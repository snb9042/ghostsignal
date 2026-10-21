import pytest
pytest.importorskip("PyQt6.QtWebEngineWidgets")
from PyQt6.QtWidgets import QApplication, QWidget
app = QApplication.instance() or QApplication([])

from ghostsignal.ui.bridge import MapBridge


class StubMapPanel(QWidget):
    """Lightweight stand-in for MapPanel that never touches QWebEngineView.

    MainWindow only needs ``bridge`` (map_clicked/marker_dragged signals)
    and these six methods; a real QWebEngineView cannot be reliably
    initialised in an offscreen/headless test environment, so tests inject
    this instead via ``MainWindow(map_panel_factory=StubMapPanel)``.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bridge = MapBridge(self)

    def set_markers(self, *a, **k): pass
    def draw_route(self, *a, **k): pass
    def draw_straight(self, *a, **k): pass
    def update_position(self, *a, **k): pass
    def clear_position(self, *a, **k): pass
    def clear_all(self, *a, **k): pass


def test_mainwindow_builds_and_plans():
    from ghostsignal.ui.main_window import MainWindow
    from ghostsignal.core.models import Waypoint
    w = MainWindow(map_panel_factory=StubMapPanel)
    w.waypoints = [Waypoint(42.0, 23.0), Waypoint(42.05, 23.05)]
    w._refresh_waypoints()
    plan = w.build_current_plan(nav_file="brdc.nav")
    # ToolConfig.resolve_tool() auto-detects a real installed binary (e.g. under
    # PothosSDR's bin dir on Windows) and returns its full path *with* the
    # platform executable suffix when one is actually installed, instead of
    # the bare command name used when nothing is found on PATH/known dirs.
    # Tolerate both so this assertion is correct on a clean CI box (bare name)
    # and on a dev machine that has the real GNSS-SDR tools installed (.exe path).
    assert (plan.gen_argv[0].endswith("gps-sdr-sim")
           or plan.gen_argv[0].endswith("gps-sdr-sim.exe")
           or plan.gen_argv[0] == "gps-sdr-sim")
    assert (plan.tx_argv[0].endswith("hackrf_transfer")
           or plan.tx_argv[0].endswith("hackrf_transfer.exe")
           or plan.tx_argv[0] == "hackrf_transfer")
