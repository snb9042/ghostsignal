"""Main application window: assembles LeftPanel/MapPanel/RightPanel in a
QSplitter plus v1's top bar / status bar / logging, and wires them to the
OSRM/pipeline/playback workers and the planning pipeline.

Reproduces v1's ``GhostSignal`` window (``ghostsignal.py`` ~lines 497-1148)
on top of the v2 panel/worker/pipeline seams built in tasks 1-18.
"""
from __future__ import annotations

import datetime
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QDateTime, pyqtSlot
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QMessageBox, QFileDialog,
)

from .left_panel import LeftPanel, TRANSPORT_KEYS
from .right_panel import RightPanel
from .map_panel import MapPanel
from .dialogs import AuthorizationDialog, SettingsDialog
from ..core.models import Waypoint, SpeedProfile, SdrConfig, Constellation, Session
from ..core import routing, motion, cli as cli_mod, session as session_mod, nmea, rinex
from ..constants import OSRM_PROFILES, SAMPLE_RATES, TRANSPORT_SPEEDS
from .. import config as config_mod
from ..config import ToolConfig, DEFAULT_TOOL_KEYS
from .. import pipeline as pipeline_mod
from ..backends.registry import build_registry
from ..sdr.hackrf import HackRfTransmitter
from ..sdr.limesdr import LimeSdrTransmitter
from ..workers.osrm_worker import OsrmWorker
from ..workers.pipeline_worker import PipelineWorker
from ..workers.playback_worker import PlaybackWorker

APP_NAME = "GhostSignal"
APP_VERSION = "2.0.0"

# Must match RightPanel's internal _CONSTELLATION_ITEMS combo order.
_CONSTELLATION_ORDER = [Constellation.GPS, Constellation.GALILEO,
                        Constellation.GLONASS, Constellation.BEIDOU]


class MainWindow(QMainWindow):
    def __init__(self, map_panel_factory=MapPanel, parent=None):
        """``map_panel_factory`` builds the map widget (default: the real
        ``MapPanel``, which owns a ``QWebEngineView``). Tests inject a
        lightweight stub exposing the same ``bridge``/``set_markers``/
        ``draw_route``/``draw_straight``/``update_position``/
        ``clear_position``/``clear_all`` surface, so constructing a
        ``MainWindow`` in an offscreen/headless test never has to spin up a
        real Chromium-backed web view. The real app calls ``MainWindow()``
        with no arguments, so behavior there is unchanged.
        """
        super().__init__(parent)
        self._map_panel_factory = map_panel_factory
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — GPS Spoof & Simulation")
        self.resize(1440, 860)
        self.setMinimumSize(1100, 720)

        self.cfg = config_mod.ToolConfig()
        self.waypoints: list[Waypoint] = []
        self.route = None
        self.constellation = Constellation.GPS
        self.nav_file = "brdc.nav"
        self.current_lat = 0.0
        self.current_lng = 0.0
        self.transmitting = False
        self._work_dir_path: str | None = None
        self._last_trajectory = None
        self._earthdata = ("", "")  # (username, password) pair for ephemeris download

        self.osrm_worker: OsrmWorker | None = None
        self.pipeline_worker: PipelineWorker | None = None
        self.playback_worker: PlaybackWorker | None = None

        self._build_ui()
        self._connect_signals()
        self._log("GhostSignal initialised", "success")
        self._log("Waiting for device...")

    # ── UI construction ─────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self._make_menu_bar()
        main_layout.addWidget(self._make_topbar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.left_panel = LeftPanel()
        self.map_panel = self._map_panel_factory(self)
        self.right_panel = RightPanel()
        splitter.addWidget(self.left_panel)
        splitter.addWidget(self.map_panel)
        splitter.addWidget(self.right_panel)
        splitter.setSizes([260, 860, 320])
        main_layout.addWidget(splitter, 1)

        self.status_bar = QLabel("STATE: IDLE  |  DEVICE: —  |  FREQ: —  |  MODE: —  |  WAYPTS: 0")
        self.status_bar.setObjectName("status_label")
        main_layout.addWidget(self.status_bar)

    def _make_menu_bar(self):
        """Create menu bar with Tools→Settings action."""
        from PyQt6.QtWidgets import QMenu
        menu_bar = self.menuBar()
        tools_menu = menu_bar.addMenu("&Tools")
        settings_action = tools_menu.addAction("&Settings")
        settings_action.triggered.connect(self._on_settings)

    def _on_settings(self):
        """Open the Settings dialog and apply changes on accept."""
        dlg = SettingsDialog(self, initial={
            k: v for k, v in self.cfg.overrides.items() if k in DEFAULT_TOOL_KEYS
        })
        if dlg.exec() == SettingsDialog.DialogCode.Accepted:
            values = dlg.values()
            # Extract tool keys and pass to ToolConfig
            tool_overrides = {k: v for k, v in values.items() if k in DEFAULT_TOOL_KEYS}
            self.cfg = ToolConfig(overrides=tool_overrides)
            # Store earthdata credentials
            self._earthdata = (values.get("earthdata_username", ""),
                             values.get("earthdata_password", ""))
            self._log("Settings updated", "success")

    def _make_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(46)
        bar.setStyleSheet("background:#0d1117; border-bottom:1px solid #1a2230;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)

        logo = QLabel("◎ GHOSTSIGNAL  <span style='color:#ffffff;opacity:0.5'>GPS SPOOF &amp; SIM</span>")
        logo.setStyleSheet("color:#00ffa3; font-size:14px; font-weight:bold; letter-spacing:2px;")
        logo.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(logo)
        layout.addStretch()

        self.time_label = QLabel()
        self.time_label.setStyleSheet("color:#00ffa3; opacity:0.6; font-size:11px;")
        layout.addWidget(self.time_label)

        self._time_timer = QTimer(self)
        self._time_timer.timeout.connect(self._update_time)
        self._time_timer.start(1000)
        self._update_time()

        self.tx_badge = QLabel("● IDLE")
        self.tx_badge.setStyleSheet(
            "color:#3a4a5a; background:#131920; border:1px solid #1a2230; "
            "padding:3px 10px; border-radius:3px; font-size:10px; letter-spacing:1px;")
        layout.addWidget(self.tx_badge)

        return bar

    def _connect_signals(self):
        lp, rp, mp = self.left_panel, self.right_panel, self.map_panel

        mp.bridge.map_clicked.connect(self._on_map_click)
        mp.bridge.marker_dragged.connect(self._on_marker_dragged)
        mp.bridge.map_right_clicked.connect(self._on_map_right_click)

        lp.signals.cleared.connect(self._on_clear)
        lp.signals.save_requested.connect(self._on_save)
        lp.signals.load_requested.connect(self._on_load)
        lp.signals.nmea_requested.connect(self._on_nmea)
        lp.signals.transport_changed.connect(self._on_transport_change)

        rp.signals.transmit_toggled.connect(self._on_transmit_toggled)
        rp.signals.constellation_changed.connect(self._on_constellation_change)
        rp.signals.freq_changed.connect(self._on_freq_change)
        rp.ephemeris_btn.clicked.connect(self._on_ephemeris_download)
        rp.save_sh_btn.clicked.connect(self._on_save_sh)

    # ── Map interaction ─────────────────────────────────────────────────

    @pyqtSlot(float, float)
    def _on_map_click(self, lat: float, lng: float):
        self.waypoints.append(Waypoint(lat, lng))
        self._refresh_waypoints()
        self._fetch_route()
        self._log(f"Waypoint {len(self.waypoints)} added: {lat:.5f}, {lng:.5f}")

    @pyqtSlot(int, float, float)
    def _on_marker_dragged(self, idx: int, lat: float, lng: float):
        if 0 <= idx < len(self.waypoints):
            self.waypoints[idx] = Waypoint(lat, lng, self.waypoints[idx].alt)
            self._refresh_waypoints()
            self._fetch_route()

    @pyqtSlot(str, float, float)
    def _on_map_right_click(self, action: str, lat: float, lng: float):
        if action == "add_waypoint":
            self.waypoints.append(Waypoint(lat, lng))
            self._refresh_waypoints(); self._fetch_route()
            self._log(f"WP {len(self.waypoints)} added (right-click): {lat:.5f}, {lng:.5f}")
        elif action == "set_start":
            if self.waypoints:
                self.waypoints[0] = Waypoint(lat, lng, self.waypoints[0].alt)
            else:
                self.waypoints.insert(0, Waypoint(lat, lng))
            self._refresh_waypoints(); self._fetch_route()
            self._log(f"Start point set: {lat:.5f}, {lng:.5f}", "success")
        elif action == "set_end":
            if len(self.waypoints) > 1:
                self.waypoints[-1] = Waypoint(lat, lng, self.waypoints[-1].alt)
            else:
                self.waypoints.append(Waypoint(lat, lng))
            self._refresh_waypoints(); self._fetch_route()
            self._log(f"End point set: {lat:.5f}, {lng:.5f}", "warn")
        elif action == "copy_coords":
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(f"{lat:.6f}, {lng:.6f}")
            self._log(f"Copied: {lat:.6f}, {lng:.6f}")

    def _refresh_waypoints(self):
        """Sync the waypoint list/count/markers/CLI/status to ``self.waypoints``.

        Deliberately does *not* touch routing/workers — callers that mutate
        waypoints kick off a route fetch separately (see ``_on_map_click``),
        so this stays safe to call directly (e.g. after a programmatic
        ``self.waypoints = [...]`` assignment in tests).
        """
        self.left_panel.wp_list.clear()
        self.left_panel.wp_count_label.setText(f"({len(self.waypoints)})")
        for i, wp in enumerate(self.waypoints):
            self.left_panel.wp_list.addItem(f"{i + 1}  {wp.lat:.5f}, {wp.lng:.5f}")
        self.map_panel.set_markers(self.waypoints)
        self._update_cli()
        self._update_status()

    def _on_clear(self):
        self.waypoints = []
        self.route = None
        self._refresh_waypoints()
        self.map_panel.clear_all()
        self.left_panel.route_stats.setText("Click map to add waypoints")
        self._log("Waypoints cleared", "warn")

    # ── Routing ──────────────────────────────────────────────────────────

    def _transport(self) -> str:
        return TRANSPORT_KEYS[self.left_panel.transport_combo.currentIndex()]

    def _fetch_route(self):
        if len(self.waypoints) < 2:
            return
        transport = self._transport()
        profile = OSRM_PROFILES.get(transport)
        if profile is None:
            # plane/boat — straight line, no OSRM round trip needed.
            self.map_panel.draw_straight(self.waypoints)
            self._on_route_ready(routing.build_route(self.waypoints, transport))
            return

        if self.osrm_worker is not None and self.osrm_worker.isRunning():
            self.osrm_worker.terminate()
            self.osrm_worker.wait()

        self.osrm_worker = OsrmWorker(list(self.waypoints), transport)
        self.osrm_worker.route_ready.connect(self._on_route_ready)
        self.osrm_worker.route_failed.connect(lambda msg: self._log(f"Route failed: {msg}", "error"))
        self.osrm_worker.start()

    def _on_route_ready(self, route):
        self.route = route
        if route.geometry:
            self.map_panel.draw_route(route.geometry)
        dur = self._fmt_duration(self._route_duration_s())
        self.left_panel.route_stats.setText(f"{route.distance_km:.2f} km  ·  ~{dur}")
        self._log(f"Route: {route.distance_km:.2f} km, ~{dur}", "success")
        self._update_cli()
        self._update_status()

    def _route_duration_s(self) -> float:
        if self.route is None or self.route.distance_km <= 0:
            return 0.0
        speed_kmh = self.left_panel.cruise_spin.value()
        return (self.route.distance_km / speed_kmh) * 3600 if speed_kmh > 0 else 0.0

    def _on_transport_change(self, transport: str):
        self.left_panel.cruise_spin.setValue(TRANSPORT_SPEEDS.get(transport, 60))
        if len(self.waypoints) >= 2:
            self._fetch_route()
        self._update_cli()
        self._update_status()

    # ── Constellation / frequency ───────────────────────────────────────

    def _on_constellation_change(self, key: str):
        self.constellation = Constellation(key)
        self._update_cli()

    def _on_freq_change(self, _mhz: float):
        self._update_cli()
        self._update_status()

    # ── Plan building (shared by CLI preview + real transmit) ──────────

    def _current_speed_profile(self) -> SpeedProfile:
        lp = self.left_panel
        randomise = lp.randomise_chk.isChecked()
        variance = float(lp.variance_slider.value())
        kind = lp.speed_profile_kind()
        if kind == "trapezoidal":
            return SpeedProfile("trapezoidal", float(lp.cruise_spin.value()),
                                accel_ms2=lp.accel_spin.value(), decel_ms2=lp.decel_spin.value(),
                                randomise=randomise, variance_pct=variance)
        return SpeedProfile("constant", float(lp.cruise_spin.value()),
                            randomise=randomise, variance_pct=variance)

    def _current_sdr_config(self) -> SdrConfig:
        rp = self.right_panel
        freq_hz = int(round(rp.freq_spin.value() * 1e6))
        sample_rate = SAMPLE_RATES[rp.sr_combo.currentIndex()]
        return SdrConfig(device=rp.device_combo.currentText(),
                         constellation=self.constellation, freq_hz=freq_hz,
                         sample_rate_hz=sample_rate, tx_gain_db=rp.gain_slider.value())

    def _current_transmitter(self):
        if self.right_panel.device_combo.currentText() == "LimeSDR":
            return LimeSdrTransmitter(self.cfg.resolve_tool("soapy"))
        return HackRfTransmitter(self.cfg.resolve_tool("hackrf"))

    def _start_time_cli(self) -> str:
        """gps-sdr-sim's ``-T`` format: ``YYYY/MM/DD,HH:MM:SS``."""
        return self.left_panel.start_time.dateTime().toString("yyyy/MM/dd,HH:mm:ss")

    def _start_time_iso(self) -> str:
        iso = self.left_panel.start_time.dateTime().toString(Qt.DateFormat.ISODate)
        return iso if iso.endswith("Z") else iso + "Z"

    def _work_dir(self) -> str:
        if self._work_dir_path is None:
            self._work_dir_path = tempfile.mkdtemp(prefix="ghostsignal_")
        return self._work_dir_path

    def _build_route_and_trajectory(self):
        """Rebuild route+trajectory from the current waypoints/transport/speed.

        Used by both ``build_current_plan`` and the real-transmit path so
        they never disagree; caches the result on ``self`` for display.
        """
        transport = self._transport()
        route = routing.build_route(self.waypoints, transport)
        self.route = route
        traj = motion.build_trajectory(route, self._current_speed_profile())
        self._last_trajectory = traj
        return route, traj

    def build_current_plan(self, nav_file: str) -> pipeline_mod.PipelinePlan:
        """Build a :class:`~ghostsignal.pipeline.PipelinePlan` for the current
        waypoints/transport/speed/constellation/device/frequency state.
        """
        _route, traj = self._build_route_and_trajectory()
        registry = build_registry(self.cfg)
        generator = registry[self.constellation]
        transmitter = self._current_transmitter()
        sdr = self._current_sdr_config()
        return pipeline_mod.plan_pipeline(
            generator=generator, transmitter=transmitter, sdr=sdr,
            trajectory=traj, nav_file=nav_file, start_time=self._start_time_cli(),
            work_dir=self._work_dir())

    # ── CLI preview ──────────────────────────────────────────────────────

    def _update_cli(self):
        if not self.waypoints:
            self.right_panel.cli_text.setPlainText("# Add waypoints to generate command")
            return
        registry = build_registry(self.cfg)
        generator = registry[self.constellation]
        transmitter = self._current_transmitter()
        sdr = self._current_sdr_config()
        duration_s = max(int(self._route_duration_s()), 60)
        script = cli_mod.build_script(
            generator=generator, transmitter=transmitter, nav_file=self.nav_file,
            motion_file="motion.csv", motion_fmt="llh", start_time=self._start_time_cli(),
            duration_s=duration_s, sdr=sdr,
            planner_note=self.right_panel.planner_only_checkbox.isChecked())
        self.right_panel.cli_text.setPlainText(script)

    def _on_save_sh(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Script", "ghostsignal_run.sh", "Shell Scripts (*.sh)")
        if path:
            Path(path).write_text(self.right_panel.cli_text.toPlainText(), encoding="utf-8")
            self._log(f"Script saved: {path}", "success")

    # ── Transmit ─────────────────────────────────────────────────────────

    def _on_transmit_toggled(self, requested: bool):
        if requested:
            self._start_transmit()
        else:
            self._stop_transmit()

    def _start_transmit(self):
        if not self.waypoints:
            QMessageBox.warning(self, "No Waypoints", "Add at least one waypoint on the map.")
            self.right_panel.set_transmitting(False)
            return

        if self.right_panel.planner_only_checkbox.isChecked():
            # Spec safety gate: generate/preview the script only, never key the transmitter.
            self._update_cli()
            self._log("Planner-only: generated CLI script (transmitter not keyed)", "info")
            self.right_panel.set_transmitting(False)
            return

        if not AuthorizationDialog.confirm(self):
            self._log("Transmit authorization declined", "warn")
            self.right_panel.set_transmitting(False)
            return

        Path(self._work_dir()).mkdir(parents=True, exist_ok=True)
        plan = self.build_current_plan(self.nav_file)
        trajectory = self._last_trajectory

        self.pipeline_worker = PipelineWorker(plan)
        self.playback_worker = PlaybackWorker(trajectory)
        self.pipeline_worker.log.connect(lambda msg: self._log(msg, "info"))
        self.pipeline_worker.stage.connect(self._on_stage)
        self.pipeline_worker.finished_rc.connect(self._on_pipeline_finished)
        self.playback_worker.position.connect(self._on_position_update)

        self.transmitting = True
        self.right_panel.set_transmitting(True)
        self._update_tx_badge(True)
        self._log("▶ Transmitting GPS signal", "success")
        self._log(
            f"  device={self.right_panel.device_combo.currentText()}  "
            f"freq={self.right_panel.freq_spin.value():.3f}MHz  "
            f"gain={self.right_panel.gain_slider.value()}dB", "info")

        self.pipeline_worker.start()
        self.playback_worker.start()

    def _stop_transmit(self):
        if self.pipeline_worker is not None:
            self.pipeline_worker.stop()
            self.pipeline_worker.wait()
            self.pipeline_worker = None
        if self.playback_worker is not None:
            self.playback_worker.stop()
            self.playback_worker.wait()
            self.playback_worker = None
        self.transmitting = False
        self.right_panel.set_transmitting(False)
        self._update_tx_badge(False)
        self.map_panel.clear_position()
        self._log("■ Transmission stopped", "warn")
        self._update_status()

    def _on_stage(self, stage: str):
        self._log(f"[{stage}]", "info")
        self._update_status()

    def _on_position_update(self, lat: float, lng: float, pct: float):
        self.current_lat = lat
        self.current_lng = lng
        self.map_panel.update_position(lat, lng)
        self.right_panel.progress_bar.setValue(int(pct))
        self._update_status()

    def _on_pipeline_finished(self, rc: int):
        # finished_rc is emitted as the last line of PipelineWorker.run(), and
        # PlaybackWorker.stop() only sets a flag that run() checks after its
        # time.sleep(0.2) -- so both threads can still be alive for a moment
        # here. Mirror _stop_transmit's wait()+null-out so a fast re-transmit
        # can never drop the only reference to a still-running QThread (which
        # would raise "QThread: Destroyed while thread is still running").
        if self.playback_worker is not None:
            self.playback_worker.stop()
            self.playback_worker.wait()
            self.playback_worker = None
        if self.pipeline_worker is not None:
            self.pipeline_worker.wait()
            self.pipeline_worker = None
        self.transmitting = False
        self.right_panel.set_transmitting(False)
        self._update_tx_badge(False)
        self.map_panel.clear_position()
        if rc == 0:
            self._log("Simulation complete", "success")
        else:
            self._log(f"Pipeline exited with code {rc}", "error")
        self._update_status()

    # ── Ephemeris download ──────────────────────────────────────────────

    def _on_ephemeris_download(self):
        date = self.left_panel.start_time.dateTime().toPyDateTime().date()
        self._log(f"Downloading ephemeris for {date.isoformat()}...", "info")
        try:
            path = rinex.ensure_ephemeris(date, config_mod.cache_dir())
        except Exception as e:
            self._log(f"Ephemeris download failed: {e}", "error")
            return
        self.nav_file = path
        self._log(f"Ephemeris ready: {path}", "success")
        self._update_cli()

    # ── NMEA import ──────────────────────────────────────────────────────

    def _on_nmea(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load NMEA Log", "", "NMEA Logs (*.nmea *.txt *.log);;All Files (*)")
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            route = nmea.parse_nmea_track(text)
        except Exception as e:
            self._log(f"NMEA load failed: {e}", "error")
            return
        self.waypoints = list(route.waypoints)
        self.route = route
        self._refresh_waypoints()
        if route.geometry:
            self.map_panel.draw_route(route.geometry)
        dur = self._fmt_duration(self._route_duration_s())
        self.left_panel.route_stats.setText(f"{route.distance_km:.2f} km  ·  ~{dur}")
        self._log(f"NMEA track loaded: {len(self.waypoints)} fixes, {route.distance_km:.2f} km", "success")

    # ── Session save/load ────────────────────────────────────────────────

    def _on_save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Session", "session.json", "JSON (*.json)")
        if not path:
            return
        s = Session(name=self.left_panel.session_name.text(), transport=self._transport(),
                   speed_profile=self._current_speed_profile(), start_time_utc=self._start_time_iso(),
                   waypoints=list(self.waypoints), sdr=self._current_sdr_config(),
                   planner_only=self.right_panel.planner_only_checkbox.isChecked())
        session_mod.save_session(s, path)
        self._log(f"Session saved: {path}", "success")

    def _on_load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Session", "", "JSON (*.json)")
        if not path:
            return
        try:
            s = session_mod.load_session(path)
        except Exception as e:
            self._log(f"Load failed: {e}", "error")
            return

        self.left_panel.session_name.setText(s.name)
        if s.transport in TRANSPORT_KEYS:
            self.left_panel.transport_combo.setCurrentIndex(TRANSPORT_KEYS.index(s.transport))

        sp = s.speed_profile
        self.left_panel.cruise_spin.setValue(int(sp.cruise_kmh))
        is_trap = sp.kind == "trapezoidal"
        self.left_panel.speed_kind_combo.setCurrentIndex(1 if is_trap else 0)
        if is_trap:
            if sp.accel_ms2 is not None:
                self.left_panel.accel_spin.setValue(sp.accel_ms2)
            if sp.decel_ms2 is not None:
                self.left_panel.decel_spin.setValue(sp.decel_ms2)

        dt = QDateTime.fromString(s.start_time_utc.rstrip("Z"), Qt.DateFormat.ISODate)
        if dt.isValid():
            self.left_panel.start_time.setDateTime(dt)

        self.waypoints = list(s.waypoints)
        self.constellation = s.sdr.constellation
        try:
            self.right_panel.constellation_combo.setCurrentIndex(_CONSTELLATION_ORDER.index(s.sdr.constellation))
        except ValueError:
            pass
        self.right_panel.freq_spin.setValue(s.sdr.freq_hz / 1e6)
        self.right_panel.gain_slider.setValue(s.sdr.tx_gain_db)
        try:
            self.right_panel.sr_combo.setCurrentIndex(list(SAMPLE_RATES).index(s.sdr.sample_rate_hz))
        except ValueError:
            pass
        self.right_panel.device_combo.setCurrentIndex(0 if s.sdr.device == "HackRF One" else 1)
        self.right_panel.planner_only_checkbox.setChecked(s.planner_only)

        self._refresh_waypoints()
        if len(self.waypoints) >= 2:
            self._fetch_route()
        self._log(f"Session loaded: {s.name}", "success")

    # ── Logger / status / clock ──────────────────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        colors = {"info": "#4a6a8a", "warn": "#ffb800", "error": "#ff4444", "success": "#00ffa3"}
        col = colors.get(level, "#4a6a8a")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:#3a4a5a">{ts}</span> <span style="color:{col}">{msg}</span>'
        self.right_panel.log_text.append(html)
        sb = self.right_panel.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _update_status(self):
        state = "TRANSMITTING" if self.transmitting else "IDLE"
        dev = self.right_panel.device_combo.currentText().upper()
        freq = f"{self.right_panel.freq_spin.value():.3f} MHz"
        mode = self._transport().upper()
        wpts = len(self.waypoints)
        dist = f"  |  DIST: {self.route.distance_km:.2f} km" if self.route and self.route.distance_km > 0 else ""
        pos = f"  |  LAT: {self.current_lat:.6f}  LNG: {self.current_lng:.6f}" if self.transmitting else ""
        self.status_bar.setText(
            f"STATE: {state}  |  DEVICE: {dev}  |  FREQ: {freq}  |  MODE: {mode}  |  WAYPTS: {wpts}{dist}{pos}")

    def _update_tx_badge(self, active: bool):
        if active:
            self.tx_badge.setText("● TX ACTIVE")
            self.tx_badge.setStyleSheet(
                "color:#00ffa3; background:#00ffa311; border:1px solid #00ffa344; "
                "padding:3px 10px; border-radius:3px; font-size:10px; letter-spacing:1px;")
        else:
            self.tx_badge.setText("● IDLE")
            self.tx_badge.setStyleSheet(
                "color:#3a4a5a; background:#131920; border:1px solid #1a2230; "
                "padding:3px 10px; border-radius:3px; font-size:10px; letter-spacing:1px;")
        self._update_status()

    def _update_time(self):
        self.time_label.setText(datetime.datetime.now().strftime("%H:%M:%S"))

    @staticmethod
    def _fmt_duration(secs: float) -> str:
        h = int(secs // 3600)
        m = int((secs % 3600) // 60)
        s = int(secs % 60)
        if h > 0:
            return f"{h}h {m}m"
        if m > 0:
            return f"{m}m {s}s"
        return f"{s}s"
