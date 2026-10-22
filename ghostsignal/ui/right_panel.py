"""Standalone RIGHT panel widget: constellation/device/frequency/gain/sample-rate,
transmit control, progress, and the CLI/log tabs.

Reproduces v1's ``_make_right_panel`` (ghostsignal.py ~lines 674-788) as a
self-contained QWidget plus the new (v2) constellation selector, planner-only
toggle, and ephemeris-download button, with a small ``signals`` holder so a
host window can react without this widget reaching back into it.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QPushButton,
    QDoubleSpinBox, QSlider, QProgressBar, QTabWidget, QPlainTextEdit,
    QTextEdit, QCheckBox, QApplication,
)
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from .widgets import labeled_group
from ..core.models import Constellation
from ..constants import GPS_L1_HZ, GPS_L2_HZ, GPS_L5_HZ, GLONASS_L1_HZ

# (Constellation, display label) in combo order.
_CONSTELLATION_ITEMS = [
    (Constellation.GPS, "GPS"),
    (Constellation.GALILEO, "Galileo"),
    (Constellation.GLONASS, "GLONASS"),
    (Constellation.BEIDOU, "BeiDou"),
]

_SAMPLE_RATE_LABELS = ["1.0 Msps", "2.6 Msps", "4.0 Msps", "8.0 Msps"]

_FREQ_PRESETS = [("L1", GPS_L1_HZ), ("L2", GPS_L2_HZ), ("L5", GPS_L5_HZ), ("GLONASS", GLONASS_L1_HZ)]


class RightPanelSignals(QObject):
    # Carries the *requested* transmitting state (True=start, False=stop).
    # This widget does not flip its own transmitting state on click — the
    # host must call set_transmitting() once it has validated/authorized
    # the request (e.g. waypoints present, AuthorizationDialog accepted).
    transmit_toggled = pyqtSignal(bool)
    # Constellation enum value, e.g. "gps"/"galileo"/"glonass"/"beidou".
    constellation_changed = pyqtSignal(str)
    # freq_spin's raw value, in MHz (same unit the widget displays/stores).
    freq_changed = pyqtSignal(float)


class RightPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = RightPanelSignals()
        self.setFixedWidth(320)
        self.setStyleSheet("background:#0d1117; border-left:1px solid #1a2230;")
        self._transmitting = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Constellation (new in v2 — backend seam; unavailable ones are greyed via set_available)
        self.constellation_combo = QComboBox()
        for _const, label in _CONSTELLATION_ITEMS:
            self.constellation_combo.addItem(label)
        layout.addWidget(labeled_group("CONSTELLATION", self.constellation_combo))
        self.constellation_combo.currentIndexChanged.connect(self._on_constellation_change)

        # SDR device
        self.device_combo = QComboBox()
        self.device_combo.addItems(["HackRF One", "LimeSDR"])
        layout.addWidget(labeled_group("SDR DEVICE", self.device_combo))

        # Frequency
        freq_widget = QWidget()
        freq_layout = QVBoxLayout(freq_widget)
        freq_layout.setContentsMargins(0, 0, 0, 0)
        # freq_spin stores MHz as float (QSpinBox maxes at 32-bit int, GPS freqs exceed that)
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(1.0, 6000.0)
        self.freq_spin.setDecimals(3)
        self.freq_spin.setSingleStep(0.001)
        self.freq_spin.setValue(GPS_L1_HZ / 1e6)  # 1575.420
        self.freq_spin.setSuffix(" MHz")
        freq_layout.addWidget(self.freq_spin)

        preset_row = QHBoxLayout()
        self.preset_buttons: dict[str, QPushButton] = {}
        for label, hz in _FREQ_PRESETS:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-size:9px; padding:1px 4px;")
            btn.clicked.connect(lambda _checked=False, h=hz: self.freq_spin.setValue(h / 1e6))
            preset_row.addWidget(btn)
            self.preset_buttons[label] = btn
        freq_layout.addLayout(preset_row)
        layout.addWidget(labeled_group("FREQUENCY", freq_widget))
        self.freq_spin.valueChanged.connect(self.signals.freq_changed.emit)

        # TX Gain
        gain_widget = QWidget()
        gain_layout = QHBoxLayout(gain_widget)
        gain_layout.setContentsMargins(0, 0, 0, 0)
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(0, 47)
        self.gain_slider.setValue(30)
        self.gain_label = QLabel("30 dB")
        self.gain_label.setStyleSheet("color:#00ffa3; min-width:40px;")
        gain_layout.addWidget(self.gain_slider)
        gain_layout.addWidget(self.gain_label)
        self.gain_slider.valueChanged.connect(lambda v: self.gain_label.setText(f"{v} dB"))
        layout.addWidget(labeled_group("TX GAIN", gain_widget))

        # Sample rate
        self.sr_combo = QComboBox()
        self.sr_combo.addItems(_SAMPLE_RATE_LABELS)
        self.sr_combo.setCurrentIndex(1)
        layout.addWidget(labeled_group("SAMPLE RATE", self.sr_combo))

        # Planner-only toggle (spec 5.5 safety gate: generate+animate, never key the transmitter)
        self.planner_only_checkbox = QCheckBox("Planner only (do not key transmitter)")
        self.planner_only_checkbox.setChecked(True)
        layout.addWidget(self.planner_only_checkbox)

        # Ephemeris download (spec 5.7) — host wires .clicked; no logic owned here.
        self.ephemeris_btn = QPushButton("Download ephemeris")
        layout.addWidget(self.ephemeris_btn)

        # Transmit button
        self.transmit_btn = QPushButton("▶  TRANSMIT")
        self.transmit_btn.setObjectName("transmit_btn")
        self.transmit_btn.setFixedHeight(50)
        self.transmit_btn.clicked.connect(self._on_transmit_clicked)
        layout.addWidget(self.transmit_btn)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # CLI tab / log tab
        self.tabs = QTabWidget()

        cli_widget = QWidget()
        cli_layout = QVBoxLayout(cli_widget)
        self.cli_text = QPlainTextEdit()
        self.cli_text.setReadOnly(True)
        self.cli_text.setFixedHeight(130)
        self.cli_text.setPlaceholderText("# Add waypoints to generate command")
        cli_layout.addWidget(self.cli_text)
        cli_btn_row = QHBoxLayout()
        self.copy_btn = QPushButton("Copy")
        self.copy_btn.clicked.connect(self._on_copy_cli)
        self.save_sh_btn = QPushButton("Save .sh")
        cli_btn_row.addWidget(self.copy_btn)
        cli_btn_row.addWidget(self.save_sh_btn)
        cli_layout.addLayout(cli_btn_row)
        self.tabs.addTab(cli_widget, "CLI COMMAND")

        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        self.tabs.addTab(log_widget, "SYSTEM LOG")

        layout.addWidget(self.tabs, 1)

    def _on_constellation_change(self, index: int):
        key = _CONSTELLATION_ITEMS[index][0].value
        self.signals.constellation_changed.emit(key)

    def _on_transmit_clicked(self):
        # Emit the *requested* state; this widget does not self-flip — see
        # RightPanelSignals.transmit_toggled docstring.
        self.signals.transmit_toggled.emit(not self._transmitting)

    def set_transmitting(self, transmitting: bool):
        """Host-driven: reflect the actual transmitting state in the button/progress bar.

        Call this after validating a transmit_toggled(True) request (or to
        revert one that was declined/aborted), and after a transmission
        finishes or is stopped.
        """
        self._transmitting = transmitting
        if transmitting:
            self.transmit_btn.setText("■  STOP TX")
            self.transmit_btn.setObjectName("stop_btn")
        else:
            self.transmit_btn.setText("▶  TRANSMIT")
            self.transmit_btn.setObjectName("transmit_btn")
        self.transmit_btn.setStyle(self.transmit_btn.style())
        self.progress_bar.setVisible(transmitting)
        if not transmitting:
            self.progress_bar.setValue(0)

    def set_available(self, constellation, available: bool):
        """Grey out (disable) the combo row for a constellation whose backend
        isn't available, without removing it from the list.

        ``constellation`` may be a ``Constellation`` enum member or its
        string value (e.g. "glonass").
        """
        key = constellation.value if isinstance(constellation, Constellation) else str(constellation).lower()
        for idx, (const, _label) in enumerate(_CONSTELLATION_ITEMS):
            if const.value == key:
                item = self.constellation_combo.model().item(idx)
                if item is not None:
                    item.setEnabled(available)
                break

    def _on_copy_cli(self):
        QApplication.clipboard().setText(self.cli_text.toPlainText())
