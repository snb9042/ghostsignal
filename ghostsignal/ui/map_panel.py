import json, importlib.resources as res
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QUrl
from .bridge import MapBridge

def _map_html():
    return (res.files("ghostsignal.ui") / "assets" / "map.html").read_text(encoding="utf-8")

class MapPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView()
        self.bridge = MapBridge(self)
        ch = QWebChannel(self.view.page())
        ch.registerObject("pyBridge", self.bridge)
        self.view.page().setWebChannel(ch)
        self.view.page().setHtml(_map_html(), QUrl("https://ghostsignal.local/"))
        lay.addWidget(self.view)

    def _js(self, code):
        self.view.page().runJavaScript(code)

    def set_markers(self, waypoints):
        n = len(waypoints)
        js = "clearMarkers();"
        for i, w in enumerate(waypoints):
            first = "true" if i == 0 else "false"
            last = "true" if (i == n - 1 and n > 1) else "false"
            js += f"addMarker({w.lat},{w.lng},{i},{first},{last});"
        self._js(js)

    def draw_route(self, geometry):
        self._js(f"drawRoute({json.dumps(geometry)});")

    def draw_straight(self, waypoints):
        pts = [{"lat": w.lat, "lng": w.lng} for w in waypoints]
        self._js(f"drawStraightLine({json.dumps(pts)});")

    def update_position(self, lat, lng):
        self._js(f"updatePosition({lat},{lng});")

    def clear_position(self):
        self._js("clearPosition();")

    def clear_all(self):
        self._js("clearMarkers(); if(routeLayer){routeLayer.remove();routeLayer=null;} clearPosition();")
