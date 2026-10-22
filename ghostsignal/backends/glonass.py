from .base import SignalGenerator
from ..core.models import Constellation
from ..constants import GLONASS_L1_HZ

class GlonassBackend(SignalGenerator):
    """Wraps a configurable multi-GNSS simulator (default: gnss-signal-simulator-rs).
    Experimental: available() only true when the user has configured a working binary."""
    name = "gnss-multi (glonass)"
    constellation = Constellation.GLONASS
    default_freq_hz = GLONASS_L1_HZ
    constellation_flag = "glonass"
    supported_motion_formats = {"llh"}

    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file):
        return [self.binary, "--system", self.constellation_flag,
                "--ephemeris", nav_file, "--motion", motion_file,
                "--start", start_time, "--duration", str(int(duration_s)),
                "--sample-rate", str(int(sample_rate)), "--bits", str(int(iq_bits)),
                "--output", out_file]
