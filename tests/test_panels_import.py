import pytest
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

def test_panels_construct():
    from ghostsignal.ui.left_panel import LeftPanel
    from ghostsignal.ui.right_panel import RightPanel
    from ghostsignal.ui.dialogs import AuthorizationDialog, SettingsDialog
    lp, rp = LeftPanel(), RightPanel()
    assert lp.transport_combo.count() == 5
    assert rp.constellation_combo.count() == 4
    assert hasattr(AuthorizationDialog, "confirm")
    assert hasattr(SettingsDialog, "values")
    assert hasattr(lp, "randomise_chk")
    assert hasattr(lp, "variance_slider")
