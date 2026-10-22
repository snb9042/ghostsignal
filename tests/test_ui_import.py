import pytest
pytest.importorskip("PyQt6.QtWebEngineWidgets")

def test_bridge_and_map_panel_importable():
    from ghostsignal.ui.bridge import MapBridge
    from ghostsignal.ui import map_panel
    assert hasattr(MapBridge, "onMapClick")
    assert hasattr(map_panel, "MapPanel")

def test_bridge_has_right_click():
    from ghostsignal.ui.bridge import MapBridge
    assert hasattr(MapBridge, "onMapRightClick")

def test_map_html_has_channel_bootstrap_and_ctx_menu():
    import importlib.resources as res
    html = (res.files("ghostsignal.ui") / "assets" / "map.html").read_text(encoding="utf-8")
    assert "qwebchannel.js" in html           # channel script loaded
    assert "new QWebChannel" in html          # bootstrap sets window.pyBridge
    assert "onMapRightClick" in html          # right-click wired
    assert 'id="ctx-menu"' in html            # menu present
