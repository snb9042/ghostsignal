import time
from PyQt6.QtCore import QThread, pyqtSignal

class PlaybackWorker(QThread):
    position = pyqtSignal(float, float, float)
    def __init__(self, trajectory):
        super().__init__(); self.traj = trajectory; self._stop = False
    def stop(self): self._stop = True
    def run(self):
        if not self.traj: return
        total = self.traj[-1].t_s or 1.0
        start = time.time()
        while not self._stop:
            el = time.time() - start
            i = min(range(len(self.traj)), key=lambda k: abs(self.traj[k].t_s - el))
            p = self.traj[i]
            self.position.emit(p.lat, p.lng, min(el / total * 100, 100))
            if el >= total: break
            time.sleep(0.2)
