from PyQt6.QtCore import QThread, pyqtSignal
from ..core import routing

class OsrmWorker(QThread):
    route_ready = pyqtSignal(object)
    route_failed = pyqtSignal(str)
    def __init__(self, waypoints, transport):
        super().__init__(); self.waypoints = waypoints; self.transport = transport
    def run(self):
        try:
            self.route_ready.emit(routing.build_route(self.waypoints, self.transport))
        except Exception as e:
            self.route_failed.emit(str(e))
