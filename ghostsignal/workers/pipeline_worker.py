from PyQt6.QtCore import QThread, pyqtSignal, QProcess, QEventLoop

class PipelineWorker(QThread):
    log = pyqtSignal(str)
    stage = pyqtSignal(str)
    finished_rc = pyqtSignal(int)
    def __init__(self, plan):
        super().__init__(); self.plan = plan; self._proc = None; self._abort = False

    def _run_step(self, argv) -> int:
        self._proc = QProcess()
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        loop = QEventLoop()
        self._proc.readyReadStandardOutput.connect(
            lambda: self.log.emit(bytes(self._proc.readAllStandardOutput()).decode(errors="replace").rstrip()))
        self._proc.finished.connect(lambda *_: loop.quit())
        self._proc.start(argv[0], argv[1:])
        loop.exec()
        return self._proc.exitCode()

    def run(self):
        # write motion file first
        with open(self.plan.motion_path, "w", encoding="utf-8") as f:
            f.write(self.plan.motion_text)
        self.stage.emit("generate")
        if self._abort: return
        rc = self._run_step(self.plan.gen_argv)
        if rc != 0 or self._abort:
            self.finished_rc.emit(rc); return
        self.stage.emit("transmit")
        rc = self._run_step(self.plan.tx_argv)
        self.finished_rc.emit(rc)

    def stop(self):
        self._abort = True
        if self._proc:
            self._proc.kill()
