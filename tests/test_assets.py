import importlib.resources as res


def _read(name):
    return (res.files("ghostsignal.ui") / "assets" / name).read_text(encoding="utf-8")


def test_map_html_exposes_js_api():
    html = _read("map.html")
    for fn in ["function addMarker", "function clearMarkers", "function drawRoute",
               "function drawStraightLine", "function updatePosition", "function clearPosition"]:
        assert fn in html
    assert "pyBridge" in html


def test_style_qss_has_theme_colors():
    qss = _read("style.qss")
    assert "#00ffa3" in qss and "QPushButton" in qss


def test_map_html_has_doctype():
    html = (res.files("ghostsignal.ui") / "assets" / "map.html").read_text(encoding="utf-8")
    assert html.lstrip().startswith("<!DOCTYPE html>")
