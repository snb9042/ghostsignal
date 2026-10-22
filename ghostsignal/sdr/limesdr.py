from .base import SdrTransmitter

class LimeSdrTransmitter(SdrTransmitter):
    name = "LimeSDR"
    def build_argv(self, *, iq_file, freq_hz, sample_rate, gain_db):
        return [self.binary, '--args=driver=lime', "--direction=TX", "--chan=0",
                f"--freq={int(freq_hz)}", f"--rate={int(sample_rate)}",
                f"--gain={int(gain_db)}", f"--file={iq_file}"]
