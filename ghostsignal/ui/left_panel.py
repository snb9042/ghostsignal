"""Standalone LEFT panel widget: session/transport/speed/start-time/waypoints/save-load.

Reproduces v1's ``_make_left_panel`` (ghostsignal.py ~lines 576-658) as a
self-contained QWidget, plus accel/decel speed controls (new in v2, shown
only for the trapezoidal speed-profile kind) and a small ``signals`` holder
so a host window can react without this widget reaching back into it.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QComboBox, QLabel,
    QPushButton, QSpinBox, QDoubleSpinBox, QDateTimeEdit, QListWidget,
    QCheckBox, QSlider,
)
from PyQt6.QtCore import QObject, pyqtSignal, QDateTime, Qt
from .widgets import labeled_group
from ..constants import TRANSPORT_SPEEDS

# Ordered (key, display label) pairs — key order follows constants.TRANSPORT_SPEEDS
# so the combo stays in sync with the rest of the app's transport vocabulary.
_TRANSPORT_LABELS = {
    "walk": "\U0001F6B6 Walk",
    "cycle": "\U0001F6B4 Cycle",
    "drive": "\U0001F697 Drive",
    "boat": "⛵ Boat",
    "plane": "✈ Plane",
}
TRANSPORT_KEYS = list(TRANSPORT_SPEEDS.keys())


class LeftPanelSignals(QObject):
    cleared = pyqtSignal()
    save_requested = pyqtSignal()
    load_requested = pyqtSignal()
    nmea_requested = pyqtSignal()
    transport_changed = pyqtSignal(str)


class LeftPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.signals = LeftPanelSignals()
        self.setFixedWidth(260)
        self.setStyleSheet("background:#0d1117; border-right:1px solid #1a2230;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Session name
        self.session_name = QLineEdit("Session 1")
        layout.addWidget(labeled_group("SESSION", self.session_name))

        # Transport mode
        self.transport_combo = QComboBox()
        for key in TRANSPORT_KEYS:
            self.transport_combo.addItem(_TRANSPORT_LABELS[key])
        self.transport_combo.setCurrentIndex(TRANSPORT_KEYS.index("drive"))
        layout.addWidget(labeled_group("TRANSPORT MODE", self.transport_combo))
        self.transport_combo.currentIndexChanged.connect(self._on_transport_change)

        # Speed (cruise always; accel/decel only for the trapezoidal profile)
        speed_widget = QWidget()
        speed_layout = QVBoxLayout(speed_widget)
        speed_layout.setContentsMargins(0, 0, 0, 0)

        self.speed_kind_combo = QComboBox()
        self.speed_kind_combo.addItems(["Constant", "Trapezoidal"])
        speed_layout.addWidget(self.speed_kind_combo)

        cruise_row = QHBoxLayout()
        cruise_row.addWidget(QLabel("Cruise"))
        self.cruise_spin = QSpinBox()
        self.cruise_spin.setRange(1, 1000)
        self.cruise_spin.setValue(60)
        self.cruise_spin.setSuffix(" km/h")
        cruise_row.addWidget(self.cruise_spin)
        speed_layout.addLayout(cruise_row)

        self.accel_row = QWidget()
        accel_layout = QHBoxLayout(self.accel_row)
        accel_layout.setContentsMargins(0, 0, 0, 0)
        accel_layout.addWidget(QLabel("Accel"))
        self.accel_spin = QDoubleSpinBox()
        self.accel_spin.setRange(0.1, 50.0)
        self.accel_spin.setSingleStep(0.1)
        self.accel_spin.setValue(2.0)
        self.accel_spin.setSuffix(" m/s²")
        accel_layout.addWidget(self.accel_spin)
        speed_layout.addWidget(self.accel_row)

        self.decel_row = QWidget()
        decel_layout = QHBoxLayout(self.decel_row)
        decel_layout.setContentsMargins(0, 0, 0, 0)
        decel_layout.addWidget(QLabel("Decel"))
        self.decel_spin = QDoubleSpinBox()
        self.decel_spin.setRange(0.1, 50.0)
        self.decel_spin.setSingleStep(0.1)
        self.decel_spin.setValue(2.0)
        self.decel_spin.setSuffix(" m/s²")
        decel_layout.addWidget(self.decel_spin)
        speed_layout.addWidget(self.decel_row)

        # Hidden by default: speed_kind_combo starts on "Constant".
        self.accel_row.setVisible(False)
        self.decel_row.setVisible(False)
        self.speed_kind_combo.currentIndexChanged.connect(self._on_speed_kind_change)

        self.randomise_chk = QCheckBox("Randomise speed")
        speed_layout.addWidget(self.randomise_chk)

        var_row = QHBoxLayout()
        var_row.addWidget(QLabel("Variance"))
        self.variance_slider = QSlider(Qt.Orientation.Horizontal)
        self.variance_slider.setRange(1, 80)
        self.variance_slider.setValue(20)
        self.variance_slider.setEnabled(False)
        self.variance_val_lbl = QLabel("±20%")
        var_row.addWidget(self.variance_slider)
        var_row.addWidget(self.variance_val_lbl)
        speed_layout.addLayout(var_row)

        self.randomise_chk.toggled.connect(self.variance_slider.setEnabled)
        self.variance_slider.valueChanged.connect(
            lambda v: self.variance_val_lbl.setText(f"±{v}%"))

        layout.addWidget(labeled_group("SPEED", speed_widget))

        # Start time
        self.start_time = QDateTimeEdit(QDateTime.currentDateTime())
        self.start_time.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_time.setCalendarPopup(True)
        layout.addWidget(labeled_group("SIMULATION START TIME", self.start_time))

        # Waypoints
        wp_widget = QWidget()
        wp_layout = QVBoxLayout(wp_widget)
        wp_layout.setContentsMargins(0, 0, 0, 0)

        wp_header = QHBoxLayout()
        self.wp_count_label = QLabel("(0)")
        self.wp_count_label.setStyleSheet("color:#00ffa3;")
        wp_header.addWidget(self.wp_count_label)
        wp_header.addStretch()
        self.clear_btn = QPushButton("CLEAR")
        self.clear_btn.setFixedWidth(52)
        self.clear_btn.setStyleSheet(
            "font-size:9px; padding:2px 6px; color:#ff4444; border-color:#ff4444;"
        )
        self.clear_btn.clicked.connect(lambda: self.signals.cleared.emit())
        wp_header.addWidget(self.clear_btn)
        wp_layout.addLayout(wp_header)

        self.wp_list = QListWidget()
        self.wp_list.setFixedHeight(120)
        wp_layout.addWidget(self.wp_list)

        self.route_stats = QLabel("Click map to add waypoints")
        self.route_stats.setStyleSheet("color:#3a4a5a; font-size:10px;")
        self.route_stats.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wp_layout.addWidget(self.route_stats)

        layout.addWidget(labeled_group("WAYPOINTS", wp_widget))

        # Save / Load
        btn_row = QHBoxLayout()
        self.save_btn = QPushButton("\U0001F4BE Save")
        self.save_btn.clicked.connect(lambda: self.signals.save_requested.emit())
        self.load_btn = QPushButton("\U0001F4C2 Load")
        self.load_btn.clicked.connect(lambda: self.signals.load_requested.emit())
        btn_row.addWidget(self.save_btn)
        btn_row.addWidget(self.load_btn)
        layout.addLayout(btn_row)

        # Load NMEA (new in v2 — feeds nmea.py's parser instead of routing)
        self.nmea_btn = QPushButton("Load NMEA")
        self.nmea_btn.clicked.connect(lambda: self.signals.nmea_requested.emit())
        layout.addWidget(self.nmea_btn)

        layout.addStretch()

    def _on_transport_change(self, index: int):
        self.signals.transport_changed.emit(TRANSPORT_KEYS[index])

    def _on_speed_kind_change(self, _index: int):
        is_trapezoidal = self.speed_kind_combo.currentText().lower() == "trapezoidal"
        self.accel_row.setVisible(is_trapezoidal)
        self.decel_row.setVisible(is_trapezoidal)

    def speed_profile_kind(self) -> str:
        """Return "constant" or "trapezoidal" — matches ``core.models.SpeedProfile.kind``."""
        return self.speed_kind_combo.currentText().lower()
