from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

class MapBridge(QObject):
    map_clicked = pyqtSignal(float, float)
    marker_dragged = pyqtSignal(int, float, float)
    map_right_clicked = pyqtSignal(str, float, float)   # action, lat, lng

    @pyqtSlot(float, float)
    def onMapClick(self, lat, lng):
        self.map_clicked.emit(lat, lng)

    @pyqtSlot(int, float, float)
    def onMarkerDragged(self, idx, lat, lng):
        self.marker_dragged.emit(idx, lat, lng)

    @pyqtSlot(str, float, float)
    def onMapRightClick(self, action: str, lat: float, lng: float):
        self.map_right_clicked.emit(action, lat, lng)
