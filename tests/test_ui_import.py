import pytest
pytest.importorskip("PyQt6.QtWebEngineWidgets")

def test_bridge_and_map_panel_importable():
    from ghostsignal.ui.bridge import MapBridge
    from ghostsignal.ui import map_panel
    assert hasattr(MapBridge, "onMapClick")
    assert hasattr(map_panel, "MapPanel")
