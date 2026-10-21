from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

class MapBridge(QObject):
    map_clicked = pyqtSignal(float, float)
    marker_dragged = pyqtSignal(int, float, float)

    @pyqtSlot(float, float)
    def onMapClick(self, lat, lng):
        self.map_clicked.emit(lat, lng)

    @pyqtSlot(int, float, float)
    def onMarkerDragged(self, idx, lat, lng):
        self.marker_dragged.emit(idx, lat, lng)
