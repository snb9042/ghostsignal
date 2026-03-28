#!/usr/bin/env python3
"""
GhostSignal — GPS Spoof & Simulation GUI
Cross-platform PyQt6 desktop application

Requirements:
    pip install PyQt6 PyQt6-WebEngine requests

External tools (must be in PATH or configured below):
    - gps-sdr-sim   https://github.com/osqzss/gps-sdr-sim
    - hackrf_transfer  (part of hackrf package)
    - LimeSuite / SoapySDR (optional, for LimeSDR)

Usage:
    python ghostsignal.py
"""

import sys
import os
import json
import math
import random
import subprocess
import datetime
import threading
import tempfile
import urllib.request
import urllib.parse
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QLabel, QPushButton, QLineEdit, QComboBox, QSlider,
    QSpinBox, QDoubleSpinBox, QGroupBox, QListWidget, QListWidgetItem,
    QTextEdit, QProgressBar, QFileDialog, QMessageBox, QDialog,
    QDialogButtonBox, QFormLayout, QDateTimeEdit, QTabWidget,
    QScrollArea, QFrame, QSizePolicy, QCheckBox, QPlainTextEdit,
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QDateTime, QProcess, QUrl,
    QPointF, QRectF, pyqtSlot,
)
from PyQt6.QtGui import (
    QColor, QPalette, QFont, QFontDatabase, QPixmap, QPainter,
    QPen, QBrush, QIcon, QTextCursor,
)
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject

# ─── Config ──────────────────────────────────────────────────────────────────

APP_NAME = "GhostSignal"
APP_VERSION = "1.0.0"
GPS_SDR_SIM = os.environ.get("GPS_SDR_SIM", "gps-sdr-sim")
HACKRF_TRANSFER = os.environ.get("HACKRF_TRANSFER", "hackrf_transfer")
LIMESDR_TX = os.environ.get("LIMESDR_TX", "SoapySDRUtil")

GPS_L1_HZ = 1_575_420_000
GPS_L2_HZ = 1_227_600_000
GPS_L5_HZ = 1_176_450_000
GLONASS_L1_HZ = 1_602_000_000

TRANSPORT_SPEEDS = {
    "walk": 5,
    "cycle": 15,
    "drive": 60,
    "boat": 25,
    "plane": 800,
}

OSRM_PROFILES = {
    "walk": "foot",
    "cycle": "cycling",
    "drive": "driving",
    "boat": "driving",
    "plane": None,  # straight line
}

# ─── Dark Palette ─────────────────────────────────────────────────────────────

STYLE = """
QMainWindow, QDialog, QWidget {
    background-color: #090b0f;
    color: #c8d8c8;
    font-family: "JetBrains Mono", "Courier New", monospace;
    font-size: 12px;
}
QGroupBox {
    border: 1px solid #1a2230;
    border-radius: 4px;
    margin-top: 8px;
    padding-top: 8px;
    color: #00ffa3;
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #00ffa3;
}
QPushButton {
    background-color: #131920;
    border: 1px solid #1a2230;
    border-radius: 4px;
    padding: 6px 12px;
    color: #c8d8c8;
    font-family: "JetBrains Mono", monospace;
    font-size: 11px;
}
QPushButton:hover {
    border-color: #00ffa3;
    background-color: #1a2230;
    color: #00ffa3;
}
QPushButton:pressed {
    background-color: #00ffa3;
    color: #090b0f;
}
QPushButton#transmit_btn {
    background-color: rgba(0, 255, 163, 0.1);
    border: 2px solid #00ffa3;
    color: #00ffa3;
    font-size: 14px;
    font-weight: bold;
    padding: 10px;
    letter-spacing: 2px;
}
QPushButton#transmit_btn:hover {
    background-color: rgba(0, 255, 163, 0.2);
}
QPushButton#stop_btn {
    background-color: rgba(255, 68, 68, 0.1);
    border: 2px solid #ff4444;
    color: #ff4444;
    font-size: 14px;
    font-weight: bold;
    padding: 10px;
    letter-spacing: 2px;
}
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #131920;
    border: 1px solid #1a2230;
    border-radius: 3px;
    padding: 4px 8px;
    color: #c8d8c8;
    selection-background-color: #00ffa3;
    selection-color: #090b0f;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border-color: #00ffa3;
}
QComboBox::drop-down {
    border-left: 1px solid #1a2230;
}
QComboBox::down-arrow {
    image: none;
    border-left: 4px solid transparent;
    border-right: 4px solid transparent;
    border-top: 5px solid #00ffa3;
    margin-right: 4px;
}
QComboBox QAbstractItemView {
    background-color: #131920;
    border: 1px solid #1a2230;
    selection-background-color: #00ffa3;
    selection-color: #090b0f;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #1a2230;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #00ffa3;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}
QSlider::sub-page:horizontal {
    background: #00ffa3;
    border-radius: 2px;
}
QListWidget {
    background-color: #0d1117;
    border: 1px solid #1a2230;
    border-radius: 3px;
    color: #c8d8c8;
    outline: none;
}
QListWidget::item {
    padding: 4px 8px;
    border-bottom: 1px solid #1a2230;
}
QListWidget::item:selected {
    background-color: rgba(0, 255, 163, 0.1);
    color: #00ffa3;
    border-left: 2px solid #00ffa3;
}
QListWidget::item:hover {
    background-color: #1a2230;
}
QTextEdit, QPlainTextEdit {
    background-color: #0a0e14;
    border: 1px solid #1a2230;
    border-radius: 3px;
    color: #00ffa3;
    font-size: 11px;
    font-family: "JetBrains Mono", monospace;
}
QProgressBar {
    background-color: #131920;
    border: 1px solid #1a2230;
    border-radius: 3px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk {
    background-color: #00ffa3;
    border-radius: 2px;
}
QScrollBar:vertical {
    background: #0a0e14;
    width: 6px;
    border-radius: 3px;
}
QScrollBar::handle:vertical {
    background: #1a2230;
    border-radius: 3px;
}
QScrollBar::handle:vertical:hover {
    background: #00ffa3;
}
QDateTimeEdit {
    background-color: #131920;
    border: 1px solid #1a2230;
    border-radius: 3px;
    padding: 4px 8px;
    color: #c8d8c8;
}
QDateTimeEdit::up-button, QDateTimeEdit::down-button {
    background-color: #1a2230;
    border: none;
    width: 16px;
}
QLabel#section_label {
    color: #00ffa3;
    font-size: 9px;
    letter-spacing: 2px;
    font-weight: bold;
}
QLabel#status_label {
    background-color: #0d1117;
    border-top: 1px solid #1a2230;
    padding: 4px 12px;
    color: #4a6a8a;
    font-size: 10px;
}
QTabWidget::pane {
    border: 1px solid #1a2230;
    background: #0d1117;
}
QTabBar::tab {
    background: #090b0f;
    border: 1px solid #1a2230;
    padding: 4px 12px;
    color: #4a6a8a;
    font-size: 10px;
    letter-spacing: 1px;
}
QTabBar::tab:selected {
    background: #0d1117;
    color: #00ffa3;
    border-bottom-color: #0d1117;
}
QSplitter::handle {
    background: #1a2230;
    width: 1px;
}
"""

# ─── Map HTML ─────────────────────────────────────────────────────────────────

MAP_HTML = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<!-- QWebChannel bridge — MUST load before any pyBridge calls -->
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; height:100%; background:#090b0f; }
  #map { width:100%; height:100%; }
  .leaflet-control-zoom a {
    background: #131920 !important;
    color: #00ffa3 !important;
    border-color: rgba(0,255,163,0.3) !important;
  }
  .leaflet-popup-content-wrapper {
    background: #131920 !important;
    color: #00ffa3 !important;
    border: 1px solid rgba(0,255,163,0.3) !important;
    font-family: monospace;
    font-size: 11px;
  }
  .leaflet-popup-tip { background: #131920 !important; }
  /* Native right-click context menu */
  #ctx-menu {
    display: none;
    position: fixed;
    z-index: 9999;
    background: #131920;
    border: 1px solid #1a2230;
    border-radius: 4px;
    min-width: 180px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.7);
    padding: 4px 0;
    font-family: monospace;
    font-size: 11px;
  }
  #ctx-menu .ctx-header {
    color: #3a4a5a;
    font-size: 9px;
    letter-spacing: 1px;
    padding: 4px 12px 2px 12px;
    border-bottom: 1px solid #1a2230;
    margin-bottom: 3px;
  }
  #ctx-menu button {
    display: block;
    width: 100%;
    background: transparent;
    border: none;
    padding: 7px 14px;
    cursor: pointer;
    font-family: monospace;
    font-size: 11px;
    text-align: left;
    transition: background 0.1s;
  }
  #ctx-menu button:hover { background: #1a2a1a; }
  #ctx-menu .btn-wp    { color: #00ffa3; }
  #ctx-menu .btn-start { color: #00ffa3; }
  #ctx-menu .btn-end   { color: #ff4444; }
  #ctx-menu .btn-copy  { color: #888; }
  #ctx-menu .divider   { height: 1px; background: #1a2230; margin: 3px 0; }
</style>
</head>
<body>
<div id="map"></div>
<!-- Native DOM context menu (avoids Leaflet popup conflicts) -->
<div id="ctx-menu">
  <div class="ctx-header" id="ctx-coords">0.00000, 0.00000</div>
  <button class="btn-wp"    id="btn-add">&#43; Add Waypoint Here</button>
  <button class="btn-start" id="btn-start">&#9654; Set as Start Point</button>
  <button class="btn-end"   id="btn-end">&#9632; Set as End Point</button>
  <div class="divider"></div>
  <button class="btn-copy"  id="btn-copy">&#128203; Copy Coordinates</button>
</div>
<script>
// ── QWebChannel bootstrap ──────────────────────────────────────────────────
window.pyBridge = null;
new QWebChannel(qt.webChannelTransport, function(channel) {
  window.pyBridge = channel.objects.pyBridge;
  // Invalidate map size after channel is ready (fixes blank tile issue)
  if (window._map) { window._map.invalidateSize(); }
});

// ── Leaflet map ────────────────────────────────────────────────────────────
var map = L.map('map', { center:[42.7,25.5], zoom:7, contextmenu: false });
window._map = map;  // expose for invalidateSize above

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  maxZoom: 19,
  subdomains: 'abcd',
  attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap contributors'
}).addTo(map);

var markers = [];
var routeLayer = null;
var posMarker = null;

function addMarker(lat, lng, idx, isFirst, isLast) {
  var color = isFirst ? '#00ffa3' : isLast ? '#ff4444' : '#ffb800';
  var icon = L.divIcon({
    html: '<div style="width:22px;height:22px;border-radius:50%;background:' + color + '22;border:2px solid ' + color + ';display:flex;align-items:center;justify-content:center;font-size:9px;font-family:monospace;font-weight:bold;color:' + color + ';box-shadow:0 0 8px ' + color + '66;">' + (idx+1) + '</div>',
    iconSize: [22, 22], iconAnchor: [11, 11], className: ''
  });
  var m = L.marker([lat, lng], {icon: icon, draggable: true}).addTo(map);
  m.bindPopup('WP ' + (idx+1) + '<br/>' + lat.toFixed(5) + ', ' + lng.toFixed(5));
  m.on('dragend', function(e) {
    var ll = e.target.getLatLng();
    if (window.pyBridge) window.pyBridge.onMarkerDragged(idx, ll.lat, ll.lng);
  });
  markers.push(m);
}

function clearMarkers() {
  markers.forEach(function(m){ m.remove(); });
  markers = [];
}

function drawRoute(geojson) {
  if (routeLayer) { routeLayer.remove(); routeLayer = null; }
  if (!geojson) return;
  routeLayer = L.geoJSON(geojson, {
    style: { color: '#00ffa3', weight: 3, opacity: 0.85 }
  }).addTo(map);
  map.fitBounds(routeLayer.getBounds(), {padding:[30,30]});
}

function drawStraightLine(waypoints) {
  if (routeLayer) { routeLayer.remove(); routeLayer = null; }
  var latlngs = waypoints.map(function(w){ return [w.lat, w.lng]; });
  routeLayer = L.polyline(latlngs, {color:'#ff8800', weight:2, dashArray:'8 4', opacity:0.8}).addTo(map);
  if (latlngs.length > 1) map.fitBounds(routeLayer.getBounds(), {padding:[30,30]});
}

function updatePosition(lat, lng) {
  if (posMarker) { posMarker.remove(); posMarker = null; }
  var icon = L.divIcon({
    html: '<div style="width:18px;height:18px;border-radius:50%;background:#00ffa3;border:2px solid white;box-shadow:0 0 16px #00ffa3,0 0 32px #00ffa366;"></div>',
    iconSize: [18,18], iconAnchor: [9,9], className: ''
  });
  posMarker = L.marker([lat, lng], {icon:icon, zIndexOffset:1000}).addTo(map);
  map.panTo([lat, lng], {animate:true, duration:0.5});
}

function clearPosition() {
  if (posMarker) { posMarker.remove(); posMarker = null; }
}

// ── Left-click: add waypoint ───────────────────────────────────────────────
map.on('click', function(e) {
  hideCtxMenu();
  if (window.pyBridge) window.pyBridge.onMapClick(e.latlng.lat, e.latlng.lng);
});

// ── Native right-click context menu ───────────────────────────────────────
var ctxMenu = document.getElementById('ctx-menu');
var _ctxLat = 0, _ctxLng = 0;

function hideCtxMenu() {
  ctxMenu.style.display = 'none';
}

function sendCtx(action) {
  hideCtxMenu();
  if (window.pyBridge) window.pyBridge.onMapRightClick(action, _ctxLat, _ctxLng);
}

document.getElementById('btn-add').onclick   = function() { sendCtx('add_waypoint'); };
document.getElementById('btn-start').onclick = function() { sendCtx('set_start'); };
document.getElementById('btn-end').onclick   = function() { sendCtx('set_end'); };
document.getElementById('btn-copy').onclick  = function() { sendCtx('copy_coords'); };

// Hide on any click elsewhere
document.addEventListener('click', function(ev) {
  if (!ctxMenu.contains(ev.target)) hideCtxMenu();
});
document.addEventListener('keydown', function(ev) {
  if (ev.key === 'Escape') hideCtxMenu();
});

// Intercept Leaflet right-click
map.on('contextmenu', function(e) {
  e.originalEvent.preventDefault();
  e.originalEvent.stopPropagation();
  _ctxLat = e.latlng.lat;
  _ctxLng = e.latlng.lng;
  document.getElementById('ctx-coords').textContent = _ctxLat.toFixed(5) + ', ' + _ctxLng.toFixed(5);
  // Position the menu at mouse coords (fixed positioning)
  var mx = e.originalEvent.clientX;
  var my = e.originalEvent.clientY;
  ctxMenu.style.left = mx + 'px';
  ctxMenu.style.top  = my + 'px';
  ctxMenu.style.display = 'block';
  // Clamp to viewport
  var r = ctxMenu.getBoundingClientRect();
  if (r.right  > window.innerWidth)  ctxMenu.style.left = (mx - r.width)  + 'px';
  if (r.bottom > window.innerHeight) ctxMenu.style.top  = (my - r.height) + 'px';
});
</script>
</body>
</html>"""

# ─── Worker Threads ───────────────────────────────────────────────────────────

class OSRMWorker(QThread):
    """Fetch route from OSRM in background."""
    route_ready = pyqtSignal(dict, float)  # geojson, distance_km
    route_failed = pyqtSignal(str)

    def __init__(self, waypoints, profile):
        super().__init__()
        self.waypoints = waypoints
        self.profile = profile

    def run(self):
        coords = ";".join(f"{w['lng']},{w['lat']}" for w in self.waypoints)
        url = f"https://router.project-osrm.org/route/v1/{self.profile}/{coords}?overview=full&geometries=geojson"
        try:
            req = urllib.request.urlopen(url, timeout=10)
            data = json.loads(req.read())
            if data.get("routes"):
                route = data["routes"][0]
                dist_km = route["distance"] / 1000
                self.route_ready.emit(route["geometry"], dist_km)
            else:
                self.route_failed.emit("No route found")
        except Exception as e:
            self.route_failed.emit(str(e))


class SimWorker(QThread):
    """Simulate position progress along route with optional speed randomisation."""
    position_update = pyqtSignal(float, float, float, float)  # lat, lng, progress, current_speed_kmh
    finished = pyqtSignal()

    def __init__(self, waypoints, total_seconds, base_speed_kmh=60,
                 randomise=False, variance_pct=20):
        super().__init__()
        self.waypoints = waypoints
        self.total_seconds = total_seconds
        self.base_speed_kmh = base_speed_kmh
        self.randomise = randomise
        self.variance_pct = variance_pct  # ±% speed variation
        self._stop = False
        self._current_speed = base_speed_kmh

    def stop(self):
        self._stop = True

    def run(self):
        import time
        wps = self.waypoints
        n = len(wps)

        # Build per-segment distance table for smooth interpolation
        seg_dists = []
        for i in range(n - 1):
            dlat = math.radians(wps[i+1]["lat"] - wps[i]["lat"])
            dlng = math.radians(wps[i+1]["lng"] - wps[i]["lng"])
            a = math.sin(dlat/2)**2 + math.cos(math.radians(wps[i]["lat"])) * \
                math.cos(math.radians(wps[i+1]["lat"])) * math.sin(dlng/2)**2
            seg_dists.append(6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a)))
        total_dist_km = sum(seg_dists) if seg_dists else 1.0

        # Randomiser state
        current_speed = float(self.base_speed_kmh)
        speed_change_interval = 3.0   # seconds between speed jitter
        last_speed_change = time.time()
        travelled_km = 0.0
        last_tick = time.time()

        while not self._stop:
            now = time.time()
            dt = now - last_tick
            last_tick = now

            # Apply speed randomisation — smooth random walk
            if self.randomise and (now - last_speed_change) >= speed_change_interval:
                max_delta = self.base_speed_kmh * (self.variance_pct / 100.0)
                # Gaussian jitter, clamped to ±variance_pct
                jitter = random.gauss(0, max_delta * 0.4)
                current_speed = max(1.0, current_speed + jitter)
                # Drift back toward base speed over time
                current_speed += (self.base_speed_kmh - current_speed) * 0.15
                current_speed = max(1.0, min(current_speed, self.base_speed_kmh * (1 + self.variance_pct / 100.0)))
                last_speed_change = now
            else:
                current_speed = float(self.base_speed_kmh)

            # Advance position by distance = speed × time
            dist_this_tick = (current_speed / 3600.0) * dt  # km
            travelled_km = min(travelled_km + dist_this_tick, total_dist_km)
            pct = (travelled_km / total_dist_km) * 100.0 if total_dist_km > 0 else 100.0

            # Find current segment and interpolate lat/lng
            cum = 0.0
            lat, lng = wps[0]["lat"], wps[0]["lng"]
            for i, sd in enumerate(seg_dists):
                if cum + sd >= travelled_km or i == len(seg_dists) - 1:
                    if sd > 0:
                        t = (travelled_km - cum) / sd
                        t = max(0.0, min(1.0, t))
                        lat = wps[i]["lat"] + t * (wps[i+1]["lat"] - wps[i]["lat"])
                        lng = wps[i]["lng"] + t * (wps[i+1]["lng"] - wps[i]["lng"])
                    else:
                        lat, lng = wps[i]["lat"], wps[i]["lng"]
                    break
                cum += sd

            self.position_update.emit(lat, lng, pct, current_speed)

            if pct >= 100.0:
                break
            time.sleep(0.25)

        self.finished.emit()


class HackRFProcess(QThread):
    """Run hackrf_transfer (or gps-sdr-sim) as subprocess, stream output."""
    output = pyqtSignal(str)
    finished = pyqtSignal(int)  # return code

    def __init__(self, cmd):
        super().__init__()
        self.cmd = cmd
        self._proc = None

    def stop(self):
        if self._proc:
            self._proc.terminate()

    def run(self):
        try:
            self._proc = subprocess.Popen(
                self.cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1
            )
            for line in self._proc.stdout:
                self.output.emit(line.rstrip())
            self._proc.wait()
            self.finished.emit(self._proc.returncode)
        except Exception as e:
            self.output.emit(f"[ERROR] {e}")
            self.finished.emit(-1)


# ─── Bridge for JS ↔ Python ──────────────────────────────────────────────────

class MapBridge(QObject):
    """Exposed to JavaScript via QWebChannel."""
    map_clicked = pyqtSignal(float, float)
    marker_dragged = pyqtSignal(int, float, float)
    map_right_clicked = pyqtSignal(str, float, float)  # action, lat, lng

    def __init__(self, parent=None):
        super().__init__(parent)

    @pyqtSlot(float, float)
    def onMapClick(self, lat: float, lng: float):
        self.map_clicked.emit(lat, lng)

    @pyqtSlot(int, float, float)
    def onMarkerDragged(self, idx: int, lat: float, lng: float):
        self.marker_dragged.emit(idx, lat, lng)

    @pyqtSlot(str, float, float)
    def onMapRightClick(self, action: str, lat: float, lng: float):
        self.map_right_clicked.emit(action, lat, lng)


# ─── Main Window ─────────────────────────────────────────────────────────────

class GhostSignal(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION} — GPS Spoof & Simulation")
        self.resize(1440, 860)
        self.setMinimumSize(1100, 720)

        self.waypoints: list[dict] = []  # [{lat, lng}]
        self.route_geojson = None
        self.route_distance_km = 0.0
        self.route_duration_s = 0.0
        self.sim_worker: SimWorker | None = None
        self.hackrf_worker: HackRFProcess | None = None
        self.osrm_worker: OSRMWorker | None = None
        self.transmitting = False
        self.current_lat = 0.0
        self.current_lng = 0.0
        self.current_speed = 0.0

        self._build_ui()
        self._connect_signals()
        self._log("GhostSignal initialised", "success")
        self._log("Waiting for device...")

    # ── UI Construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        main_layout.addWidget(self._make_topbar())

        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._make_left_panel())
        splitter.addWidget(self._make_map_panel())
        splitter.addWidget(self._make_right_panel())
        splitter.setSizes([260, 860, 320])
        main_layout.addWidget(splitter, 1)

        # Status bar
        self.status_bar = QLabel("STATE: IDLE  |  DEVICE: —  |  FREQ: —  |  MODE: —  |  WAYPTS: 0")
        self.status_bar.setObjectName("status_label")
        main_layout.addWidget(self.status_bar)

    def _make_topbar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(46)
        bar.setStyleSheet("background:#0d1117; border-bottom:1px solid #1a2230;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 0, 12, 0)

        # Logo
        logo = QLabel("◎ GHOSTSIGNAL  <span style='color:#ffffff;opacity:0.5'>GPS SPOOF &amp; SIM</span>")
        logo.setStyleSheet("color:#00ffa3; font-size:14px; font-weight:bold; letter-spacing:2px;")
        logo.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(logo)
        layout.addStretch()

        # Time
        self.time_label = QLabel()
        self.time_label.setStyleSheet("color:#00ffa3; opacity:0.6; font-size:11px;")
        layout.addWidget(self.time_label)

        timer = QTimer(self)
        timer.timeout.connect(self._update_time)
        timer.start(1000)
        self._update_time()

        # TX badge
        self.tx_badge = QLabel("● IDLE")
        self.tx_badge.setStyleSheet("color:#3a4a5a; background:#131920; border:1px solid #1a2230; padding:3px 10px; border-radius:3px; font-size:10px; letter-spacing:1px;")
        layout.addWidget(self.tx_badge)

        return bar

    def _make_left_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(260)
        panel.setStyleSheet("background:#0d1117; border-right:1px solid #1a2230;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Session name
        grp = QGroupBox("SESSION")
        g_l = QVBoxLayout(grp)
        self.session_name = QLineEdit("Session 1")
        g_l.addWidget(self.session_name)
        layout.addWidget(grp)

        # Transport
        grp2 = QGroupBox("TRANSPORT MODE")
        g_l2 = QVBoxLayout(grp2)
        self.transport_combo = QComboBox()
        self.transport_combo.addItems(["🚶 Walk", "🚴 Cycle", "🚗 Drive", "⛵ Boat", "✈ Plane"])
        self.transport_combo.setCurrentIndex(2)
        g_l2.addWidget(self.transport_combo)
        layout.addWidget(grp2)

        # Speed
        grp3 = QGroupBox("SPEED")
        g_l3 = QVBoxLayout(grp3)
        spd_row = QHBoxLayout()
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(1, 1000)
        self.speed_spin.setValue(60)
        self.speed_spin.setSuffix(" km/h")
        spd_row.addWidget(self.speed_spin)
        g_l3.addLayout(spd_row)

        # Randomiser
        self.randomise_chk = QCheckBox("Randomise speed")
        self.randomise_chk.setStyleSheet("color:#00ffa3; font-size:11px;")
        g_l3.addWidget(self.randomise_chk)

        variance_row = QHBoxLayout()
        variance_lbl = QLabel("Variance:")
        variance_lbl.setStyleSheet("color:#4a6a8a; font-size:10px;")
        self.variance_slider = QSlider(Qt.Orientation.Horizontal)
        self.variance_slider.setRange(1, 80)
        self.variance_slider.setValue(20)
        self.variance_slider.setEnabled(False)
        self.variance_val_lbl = QLabel("±20%")
        self.variance_val_lbl.setStyleSheet("color:#ffb800; font-size:10px; min-width:32px;")
        variance_row.addWidget(variance_lbl)
        variance_row.addWidget(self.variance_slider)
        variance_row.addWidget(self.variance_val_lbl)
        g_l3.addLayout(variance_row)
        layout.addWidget(grp3)

        # Wire randomiser toggle
        self.randomise_chk.toggled.connect(self.variance_slider.setEnabled)
        self.variance_slider.valueChanged.connect(
            lambda v: self.variance_val_lbl.setText(f"\u00b1{v}%")
        )

        # Start time
        grp4 = QGroupBox("SIMULATION START TIME")
        g_l4 = QVBoxLayout(grp4)
        self.start_time = QDateTimeEdit(QDateTime.currentDateTime())
        self.start_time.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time.setCalendarPopup(True)
        g_l4.addWidget(self.start_time)
        layout.addWidget(grp4)

        # Waypoints
        grp5 = QGroupBox("WAYPOINTS")
        g_l5 = QVBoxLayout(grp5)
        wp_header = QHBoxLayout()
        self.wp_count_label = QLabel("(0)")
        self.wp_count_label.setStyleSheet("color:#00ffa3;")
        wp_header.addWidget(self.wp_count_label)
        wp_header.addStretch()
        clear_btn = QPushButton("CLEAR")
        clear_btn.setFixedWidth(52)
        clear_btn.setStyleSheet("font-size:9px; padding:2px 6px; color:#ff4444; border-color:#ff4444;")
        clear_btn.clicked.connect(self._clear_waypoints)
        wp_header.addWidget(clear_btn)
        g_l5.addLayout(wp_header)

        self.wp_list = QListWidget()
        self.wp_list.setFixedHeight(120)
        g_l5.addWidget(self.wp_list)

        # Route stats
        self.route_stats = QLabel("Click map to add waypoints")
        self.route_stats.setStyleSheet("color:#3a4a5a; font-size:10px;")
        self.route_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        g_l5.addWidget(self.route_stats)
        layout.addWidget(grp5)

        # Save/Load
        btn_row = QHBoxLayout()
        save_btn = QPushButton("💾 Save")
        save_btn.clicked.connect(self._save_session)
        load_btn = QPushButton("📂 Load")
        load_btn.clicked.connect(self._load_session)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(load_btn)
        layout.addLayout(btn_row)

        layout.addStretch()
        return panel

    def _make_map_panel(self) -> QWidget:
        self.web_view = QWebEngineView()
        self.bridge = MapBridge(self)

        channel = QWebChannel(self.web_view.page())
        channel.registerObject("pyBridge", self.bridge)
        self.web_view.page().setWebChannel(channel)

        # Inject QWebChannel JS support
        # Use a real https base URL so WebEngine sends a valid Referer to tile servers
        self.web_view.page().setHtml(MAP_HTML, QUrl("https://ghostsignal.local/"))

        return self.web_view

    def _make_right_panel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(320)
        panel.setStyleSheet("background:#0d1117; border-left:1px solid #1a2230;")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Device
        grp_dev = QGroupBox("SDR DEVICE")
        g_dev = QHBoxLayout(grp_dev)
        self.device_combo = QComboBox()
        self.device_combo.addItems(["HackRF One", "LimeSDR"])
        g_dev.addWidget(self.device_combo)
        layout.addWidget(grp_dev)

        # Frequency
        grp_freq = QGroupBox("FREQUENCY")
        g_freq = QVBoxLayout(grp_freq)
        freq_row = QHBoxLayout()
        # freq_spin stores MHz as float (QSpinBox maxes at 32-bit int, GPS freqs exceed that)
        self.freq_spin = QDoubleSpinBox()
        self.freq_spin.setRange(1.0, 6000.0)
        self.freq_spin.setDecimals(3)
        self.freq_spin.setSingleStep(0.001)
        self.freq_spin.setValue(GPS_L1_HZ / 1e6)  # 1575.420
        self.freq_spin.setSuffix(" MHz")
        freq_row.addWidget(self.freq_spin)
        g_freq.addLayout(freq_row)

        preset_row = QHBoxLayout()
        for label, hz in [("L1", GPS_L1_HZ), ("L2", GPS_L2_HZ), ("L5", GPS_L5_HZ), ("GLONASS", GLONASS_L1_HZ)]:
            btn = QPushButton(label)
            btn.setFixedHeight(22)
            btn.setStyleSheet("font-size:9px; padding:1px 4px;")
            btn.clicked.connect(lambda _, h=hz: self.freq_spin.setValue(h / 1e6))
            preset_row.addWidget(btn)
        g_freq.addLayout(preset_row)
        layout.addWidget(grp_freq)

        # TX Gain
        grp_gain = QGroupBox("TX GAIN")
        g_gain = QVBoxLayout(grp_gain)
        gain_row = QHBoxLayout()
        self.gain_slider = QSlider(Qt.Orientation.Horizontal)
        self.gain_slider.setRange(0, 47)
        self.gain_slider.setValue(30)
        self.gain_label = QLabel("30 dB")
        self.gain_label.setStyleSheet("color:#00ffa3; min-width:40px;")
        gain_row.addWidget(self.gain_slider)
        gain_row.addWidget(self.gain_label)
        g_gain.addLayout(gain_row)
        layout.addWidget(grp_gain)

        # Sample Rate
        grp_sr = QGroupBox("SAMPLE RATE")
        g_sr = QHBoxLayout(grp_sr)
        self.sr_combo = QComboBox()
        self.sr_combo.addItems(["1.0 Msps", "2.6 Msps", "4.0 Msps", "8.0 Msps"])
        self.sr_combo.setCurrentIndex(1)
        g_sr.addWidget(self.sr_combo)
        layout.addWidget(grp_sr)

        # Transmit button
        self.transmit_btn = QPushButton("▶  TRANSMIT")
        self.transmit_btn.setObjectName("transmit_btn")
        self.transmit_btn.setFixedHeight(50)
        self.transmit_btn.clicked.connect(self._on_transmit)
        layout.addWidget(self.transmit_btn)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # CLI tab / log tab
        tabs = QTabWidget()

        # CLI tab
        cli_widget = QWidget()
        cli_layout = QVBoxLayout(cli_widget)
        self.cli_text = QPlainTextEdit()
        self.cli_text.setReadOnly(True)
        self.cli_text.setFixedHeight(130)
        self.cli_text.setPlaceholderText("# Add waypoints to generate command")
        cli_layout.addWidget(self.cli_text)
        cli_btn_row = QHBoxLayout()
        copy_btn = QPushButton("Copy")
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.cli_text.toPlainText()))
        save_sh_btn = QPushButton("Save .sh")
        save_sh_btn.clicked.connect(self._save_sh)
        cli_btn_row.addWidget(copy_btn)
        cli_btn_row.addWidget(save_sh_btn)
        cli_layout.addLayout(cli_btn_row)
        tabs.addTab(cli_widget, "CLI COMMAND")

        # Log tab
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        tabs.addTab(log_widget, "SYSTEM LOG")

        layout.addWidget(tabs, 1)

        # Attribution
        attr = QLabel('<a href="https://www.perplexity.ai/computer" style="color:#3a4a5a;">Created with Perplexity Computer</a>')
        attr.setOpenExternalLinks(True)
        attr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        attr.setStyleSheet("font-size:10px; padding:4px;")
        layout.addWidget(attr)

        return panel

    # ── Signal Connections ────────────────────────────────────────────────────

    def _connect_signals(self):
        self.bridge.map_clicked.connect(self._on_map_click)
        self.bridge.marker_dragged.connect(self._on_marker_dragged)
        self.bridge.map_right_clicked.connect(self._on_map_right_click)
        self.transport_combo.currentIndexChanged.connect(self._on_transport_change)
        self.freq_spin.valueChanged.connect(self._on_freq_change)
        self.gain_slider.valueChanged.connect(lambda v: self.gain_label.setText(f"{v} dB"))

    # ── Map Interaction ───────────────────────────────────────────────────────

    @pyqtSlot(float, float)
    def _on_map_click(self, lat: float, lng: float):
        self.waypoints.append({"lat": lat, "lng": lng})
        self._refresh_waypoints()
        self._fetch_route()
        self._log(f"Waypoint {len(self.waypoints)} added: {lat:.5f}, {lng:.5f}")

    @pyqtSlot(int, float, float)
    def _on_marker_dragged(self, idx: int, lat: float, lng: float):
        if 0 <= idx < len(self.waypoints):
            self.waypoints[idx] = {"lat": lat, "lng": lng}
            self._fetch_route()

    @pyqtSlot(str, float, float)
    def _on_map_right_click(self, action: str, lat: float, lng: float):
        """Handle right-click context menu actions from the map."""
        # Close the popup via JS
        self.web_view.page().runJavaScript("if(ctxMenu){ctxMenu.remove();ctxMenu=null;}")

        if action == "add_waypoint":
            self.waypoints.append({"lat": lat, "lng": lng})
            self._refresh_waypoints()
            self._fetch_route()
            self._log(f"WP {len(self.waypoints)} added (right-click): {lat:.5f}, {lng:.5f}")

        elif action == "set_start":
            # Insert/replace as first waypoint
            if self.waypoints:
                self.waypoints[0] = {"lat": lat, "lng": lng}
            else:
                self.waypoints.insert(0, {"lat": lat, "lng": lng})
            self._refresh_waypoints()
            self._fetch_route()
            self._log(f"Start point set: {lat:.5f}, {lng:.5f}", "success")

        elif action == "set_end":
            # Insert/replace as last waypoint
            if len(self.waypoints) > 1:
                self.waypoints[-1] = {"lat": lat, "lng": lng}
            else:
                self.waypoints.append({"lat": lat, "lng": lng})
            self._refresh_waypoints()
            self._fetch_route()
            self._log(f"End point set: {lat:.5f}, {lng:.5f}", "warn")

        elif action == "copy_coords":
            QApplication.clipboard().setText(f"{lat:.6f}, {lng:.6f}")
            self._log(f"Copied: {lat:.6f}, {lng:.6f}")

    def _refresh_waypoints(self):
        self.wp_list.clear()
        self.wp_count_label.setText(f"({len(self.waypoints)})")
        for i, wp in enumerate(self.waypoints):
            item = QListWidgetItem(f"{i+1}  {wp['lat']:.5f}, {wp['lng']:.5f}")
            self.wp_list.addItem(item)
        self._update_map_markers()
        self._update_cli()
        self._update_status()

    def _update_map_markers(self):
        n = len(self.waypoints)
        js = "clearMarkers();"
        for i, wp in enumerate(self.waypoints):
            is_first = "true" if i == 0 else "false"
            is_last = "true" if (i == n - 1 and n > 1) else "false"
            js += f"addMarker({wp['lat']},{wp['lng']},{i},{is_first},{is_last});"
        self.web_view.page().runJavaScript(js)

    def _clear_waypoints(self):
        self.waypoints.clear()
        self.route_geojson = None
        self.route_distance_km = 0.0
        self.route_duration_s = 0.0
        self._refresh_waypoints()
        self.web_view.page().runJavaScript("clearMarkers(); if(routeLayer){routeLayer.remove();routeLayer=null;}")
        self.route_stats.setText("Click map to add waypoints")
        self._update_cli()
        self._log("Waypoints cleared", "warn")

    # ── Routing ───────────────────────────────────────────────────────────────

    def _fetch_route(self):
        if len(self.waypoints) < 2:
            return

        transport = self._get_transport()
        profile = OSRM_PROFILES.get(transport)

        if profile is None:  # plane — straight line
            latlngs = [{"lat": w["lat"], "lng": w["lng"]} for w in self.waypoints]
            js = f"drawStraightLine({json.dumps(latlngs)});"
            self.web_view.page().runJavaScript(js)
            dist = sum(
                self._haversine(self.waypoints[i], self.waypoints[i + 1])
                for i in range(len(self.waypoints) - 1)
            )
            self._on_route_ready(None, dist)
            return

        if self.osrm_worker and self.osrm_worker.isRunning():
            self.osrm_worker.terminate()

        self.osrm_worker = OSRMWorker(self.waypoints, profile)
        self.osrm_worker.route_ready.connect(self._on_route_ready)
        self.osrm_worker.route_failed.connect(lambda msg: self._log(f"Route failed: {msg}", "error"))
        self.osrm_worker.start()

    def _on_route_ready(self, geojson, dist_km: float):
        self.route_geojson = geojson
        self.route_distance_km = dist_km
        speed = self.speed_spin.value()
        self.route_duration_s = (dist_km / speed) * 3600 if speed > 0 else 0

        if geojson:
            js = f"drawRoute({json.dumps(geojson)});"
            self.web_view.page().runJavaScript(js)

        dur = self._fmt_duration(self.route_duration_s)
        self.route_stats.setText(f"{dist_km:.2f} km  ·  ~{dur}")
        self._log(f"Route: {dist_km:.2f} km, ~{dur}", "success")
        self._update_cli()

    # ── Transport / Freq ──────────────────────────────────────────────────────

    def _on_transport_change(self, idx: int):
        modes = ["walk", "cycle", "drive", "boat", "plane"]
        mode = modes[idx]
        self.speed_spin.setValue(TRANSPORT_SPEEDS.get(mode, 60))
        if len(self.waypoints) >= 2:
            self._fetch_route()
        self._update_cli()
        self._update_status()

    def _on_freq_change(self, mhz: float):
        # freq_spin now stores MHz directly
        self._update_cli()

    def _get_transport(self) -> str:
        modes = ["walk", "cycle", "drive", "boat", "plane"]
        return modes[self.transport_combo.currentIndex()]

    def _get_sample_rate(self) -> int:
        rates = [1_000_000, 2_600_000, 4_000_000, 8_000_000]
        return rates[self.sr_combo.currentIndex()]

    # ── Transmit ──────────────────────────────────────────────────────────────

    def _on_transmit(self):
        if self.transmitting:
            self._stop_transmit()
            return

        if not self.waypoints:
            QMessageBox.warning(self, "No Waypoints", "Add at least one waypoint on the map.")
            return

        self.transmitting = True
        self._update_tx_badge(True)
        self.transmit_btn.setText("■  STOP TX")
        self.transmit_btn.setObjectName("stop_btn")
        self.transmit_btn.setStyle(self.transmit_btn.style())
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        duration = max(self.route_duration_s, 60)
        randomise = self.randomise_chk.isChecked()
        variance = self.variance_slider.value()
        base_spd = self.speed_spin.value()

        self.sim_worker = SimWorker(
            self.waypoints, duration,
            base_speed_kmh=base_spd,
            randomise=randomise,
            variance_pct=variance,
        )
        self.sim_worker.position_update.connect(self._on_position_update)
        self.sim_worker.finished.connect(self._on_sim_finished)
        self.sim_worker.start()

        rand_info = f"  randomise=ON  variance=±{variance}%" if randomise else "  randomise=OFF"
        self._log("▶ Transmitting GPS signal", "success")
        self._log(f"  device={self._get_device_name()}  freq={self.freq_spin.value():.3f}MHz  gain={self.gain_slider.value()}dB", "info")
        self._log(f"  speed={base_spd}km/h{rand_info}", "info")

        # Show CLI and optionally run if tools available
        self._update_cli()

    def _stop_transmit(self):
        if self.sim_worker:
            self.sim_worker.stop()
        if self.hackrf_worker:
            self.hackrf_worker.stop()
        self.transmitting = False
        self.current_speed = 0.0
        self._update_tx_badge(False)
        self.transmit_btn.setText("▶  TRANSMIT")
        self.transmit_btn.setObjectName("transmit_btn")
        self.transmit_btn.setStyle(self.transmit_btn.style())
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.web_view.page().runJavaScript("clearPosition();")
        self._log("■ Transmission stopped", "warn")
        self._update_status()

    def _on_position_update(self, lat: float, lng: float, pct: float, speed: float):
        self.current_lat = lat
        self.current_lng = lng
        self.current_speed = speed
        self.progress_bar.setValue(int(pct))
        self.web_view.page().runJavaScript(f"updatePosition({lat},{lng});")
        self._update_status()

    def _on_sim_finished(self):
        if self.transmitting:
            self._stop_transmit()
            self._log("Simulation complete", "success")

    def _get_device_name(self) -> str:
        return "HackRF" if self.device_combo.currentIndex() == 0 else "LimeSDR"

    # ── CLI Command ───────────────────────────────────────────────────────────

    def _update_cli(self):
        if not self.waypoints:
            self.cli_text.setPlainText("# Add waypoints to generate command")
            return

        wp = self.waypoints[0]
        freq_mhz = self.freq_spin.value()          # MHz (float)
        freq_hz = int(round(freq_mhz * 1e6))       # Hz (int) for CLI args
        gain = self.gain_slider.value()
        sr = self._get_sample_rate()
        device = self.device_combo.currentIndex()
        start_dt = self.start_time.dateTime().toString("yyyy/MM/dd,HH:mm:ss")
        duration = max(int(self.route_duration_s), 60)

        lines = [
            "#!/bin/bash",
            "# GhostSignal — Auto-generated GPS simulation script",
            f"# Session: {self.session_name.text()}  |  Mode: {self._get_transport()}",
            f"# Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "# Step 1: Download RINEX navigation file (edit path as needed)",
            "# wget -O brdc.nav https://cddis.nasa.gov/archive/gnss/data/current/",
            "",
            "# Step 2: Generate GPS baseband I/Q file",
            f"gps-sdr-sim -e brdc.nav \\",
            f"  -l {wp['lat']:.7f},{wp['lng']:.7f},100 \\",
            f"  -T {start_dt} \\",
            f"  -d {duration} \\",
            f"  -o gps_sim.bin",
            "",
        ]

        if device == 0:
            lines += [
                "# Step 3: Transmit with HackRF One",
                f"hackrf_transfer -t gps_sim.bin \\",
                f"  -f {freq_hz} \\",
                f"  -s {sr} \\",
                f"  -a 1 -x {gain} \\",
                f"  -R",
            ]
        else:
            lines += [
                "# Step 3: Transmit with LimeSDR (SoapySDR)",
                f'SoapySDRUtil --args="driver=lime" \\',
                f'  --direction=TX --chan=0 \\',
                f"  --freq={freq_hz} --rate={sr} \\",
                f"  --gain={gain} --file=gps_sim.bin",
            ]

        # Add multi-waypoint note
        if len(self.waypoints) > 1:
            lines += [
                "",
                "# Multi-waypoint route: use nmea_gen or custom script",
                "# to generate sequential I/Q files and stitch them.",
            ]

        self.cli_text.setPlainText("\n".join(lines))

    def _save_sh(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Script", "ghostsignal_run.sh", "Shell Scripts (*.sh)")
        if path:
            Path(path).write_text(self.cli_text.toPlainText())
            self._log(f"Script saved: {path}", "success")

    # ── Session Save/Load ─────────────────────────────────────────────────────

    def _save_session(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Session", "session.json", "JSON (*.json)")
        if path:
            data = {
                "name": self.session_name.text(),
                "transport": self._get_transport(),
                "speed_kmh": self.speed_spin.value(),
                "start_time": self.start_time.dateTime().toString(Qt.DateFormat.ISODate),
                "waypoints": self.waypoints,
                "freq_mhz": self.freq_spin.value(),  # stored as MHz
                "gain": self.gain_slider.value(),
                "sample_rate": self._get_sample_rate(),
                "device": self.device_combo.currentIndex(),
            }
            Path(path).write_text(json.dumps(data, indent=2))
            self._log(f"Session saved: {path}", "success")

    def _load_session(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load Session", "", "JSON (*.json)")
        if path:
            try:
                data = json.loads(Path(path).read_text())
                self.session_name.setText(data.get("name", "Session"))
                modes = ["walk", "cycle", "drive", "boat", "plane"]
                t = data.get("transport", "drive")
                if t in modes:
                    self.transport_combo.setCurrentIndex(modes.index(t))
                self.speed_spin.setValue(data.get("speed_kmh", 60))
                # Support both old Hz format and new MHz format
                saved_freq = data.get("freq_mhz") or data.get("freq", GPS_L1_HZ)
                # If value looks like Hz (> 1000), convert to MHz
                if saved_freq > 1000:
                    saved_freq = saved_freq / 1e6
                self.freq_spin.setValue(saved_freq)
                self.gain_slider.setValue(data.get("gain", 30))
                self.device_combo.setCurrentIndex(data.get("device", 0))
                self.waypoints = data.get("waypoints", [])
                self._refresh_waypoints()
                if len(self.waypoints) >= 2:
                    self._fetch_route()
                self._log(f"Session loaded: {data.get('name')}", "success")
            except Exception as e:
                self._log(f"Load failed: {e}", "error")

    # ── Logger ────────────────────────────────────────────────────────────────

    def _log(self, msg: str, level: str = "info"):
        colors = {
            "info": "#4a6a8a",
            "warn": "#ffb800",
            "error": "#ff4444",
            "success": "#00ffa3",
        }
        col = colors.get(level, "#4a6a8a")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        html = f'<span style="color:#3a4a5a">{ts}</span> <span style="color:{col}">{msg}</span>'
        self.log_text.append(html)
        sb = self.log_text.verticalScrollBar()
        sb.setValue(sb.maximum())

    # ── Status ────────────────────────────────────────────────────────────────

    def _update_status(self):
        state = "TRANSMITTING" if self.transmitting else "IDLE"
        dev = self._get_device_name().upper()
        freq = f"{self.freq_spin.value():.3f} MHz"
        mode = self._get_transport().upper()
        wpts = len(self.waypoints)
        dist = f"  |  DIST: {self.route_distance_km:.2f} km" if self.route_distance_km > 0 else ""
        pos = f"  |  LAT: {self.current_lat:.6f}  LNG: {self.current_lng:.6f}" if self.transmitting else ""
        spd = f"  |  SPEED: {self.current_speed:.1f} km/h" if self.transmitting else ""
        self.status_bar.setText(f"STATE: {state}  |  DEVICE: {dev}  |  FREQ: {freq}  |  MODE: {mode}  |  WAYPTS: {wpts}{dist}{pos}{spd}")

    def _update_tx_badge(self, active: bool):
        if active:
            self.tx_badge.setText("● TX ACTIVE")
            self.tx_badge.setStyleSheet("color:#00ffa3; background:#00ffa311; border:1px solid #00ffa344; padding:3px 10px; border-radius:3px; font-size:10px; letter-spacing:1px;")
        else:
            self.tx_badge.setText("● IDLE")
            self.tx_badge.setStyleSheet("color:#3a4a5a; background:#131920; border:1px solid #1a2230; padding:3px 10px; border-radius:3px; font-size:10px; letter-spacing:1px;")
        self._update_status()

    def _update_time(self):
        self.time_label.setText(datetime.datetime.now().strftime("%H:%M:%S"))

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _haversine(a: dict, b: dict) -> float:
        R = 6371
        dLat = math.radians(b["lat"] - a["lat"])
        dLng = math.radians(b["lng"] - a["lng"])
        x = (math.sin(dLat / 2) ** 2 +
             math.cos(math.radians(a["lat"])) *
             math.cos(math.radians(b["lat"])) *
             math.sin(dLng / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(x), math.sqrt(1 - x))

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


# ─── Entry point ─────────────────────────────────────────────────────────────

def main():
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setStyleSheet(STYLE)

    # Apply dark palette
    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window, QColor("#090b0f"))
    pal.setColor(QPalette.ColorRole.WindowText, QColor("#c8d8c8"))
    pal.setColor(QPalette.ColorRole.Base, QColor("#131920"))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor("#0d1117"))
    pal.setColor(QPalette.ColorRole.ToolTipBase, QColor("#131920"))
    pal.setColor(QPalette.ColorRole.ToolTipText, QColor("#c8d8c8"))
    pal.setColor(QPalette.ColorRole.Text, QColor("#c8d8c8"))
    pal.setColor(QPalette.ColorRole.Button, QColor("#131920"))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor("#c8d8c8"))
    pal.setColor(QPalette.ColorRole.BrightText, QColor("#00ffa3"))
    pal.setColor(QPalette.ColorRole.Link, QColor("#00ffa3"))
    pal.setColor(QPalette.ColorRole.Highlight, QColor("#00ffa3"))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#090b0f"))
    app.setPalette(pal)

    win = GhostSignal()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
