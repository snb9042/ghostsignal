from .base import SdrTransmitter

class HackRfTransmitter(SdrTransmitter):
    name = "HackRF One"
    def build_argv(self, *, iq_file, freq_hz, sample_rate, gain_db):
        return [self.binary, "-t", iq_file, "-f", str(int(freq_hz)),
                "-s", str(int(sample_rate)), "-a", "1", "-x", str(int(gain_db)), "-R"]
