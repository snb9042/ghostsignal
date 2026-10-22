from .base import SignalGenerator
from ..core.models import Constellation
from ..constants import GPS_L1_HZ

_FMT_FLAG = {"llh": "-x", "ecef": "-u", "nmea": "-g"}

class GpsSdrSim(SignalGenerator):
    name = "gps-sdr-sim"
    constellation = Constellation.GPS
    default_freq_hz = GPS_L1_HZ
    supported_motion_formats = {"llh", "ecef", "nmea"}

    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file):
        argv = [self.binary, "-e", nav_file,
                _FMT_FLAG[motion_fmt], motion_file,
                "-T", start_time, "-d", str(int(duration_s)),
                "-s", str(int(sample_rate)), "-b", str(int(iq_bits)),
                "-o", out_file]
        if iono:
            argv.append("-i")
        return argv
