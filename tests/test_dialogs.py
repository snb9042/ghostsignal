import pytest
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from ghostsignal.ui.dialogs import AuthorizationDialog, SettingsDialog
from ghostsignal.config import DEFAULT_TOOL_KEYS, ToolConfig

def test_authorization_gate_requires_checkbox():
    d = AuthorizationDialog()
    # OK disabled until the authorization checkbox is ticked
    assert d.ok_button.isEnabled() is False
    d.confirm_checkbox.setChecked(True)
    assert d.ok_button.isEnabled() is True

def test_settings_values_shape_and_blank_autodetect(monkeypatch):
    monkeypatch.delenv("GPS_SDR_SIM", raising=False)
    d = SettingsDialog()
    vals = d.values()
    assert set(vals) == set(DEFAULT_TOOL_KEYS) | {"earthdata_username", "earthdata_password"}
    # untouched (blank) tool fields must NOT disable auto-detection
    assert ToolConfig(vals).resolve_tool("gps") == "gps-sdr-sim"
