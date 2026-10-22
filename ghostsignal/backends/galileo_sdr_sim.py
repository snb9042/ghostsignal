from .base import SignalGenerator
from ..core.models import Constellation
from ..constants import GALILEO_E1_HZ

class GalileoSdrSim(SignalGenerator):
    name = "galileo-sdr-sim"
    constellation = Constellation.GALILEO
    default_freq_hz = GALILEO_E1_HZ
    supported_motion_formats = {"llh", "ecef"}

    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file):
        # galileo-sdr-sim mirrors gps-sdr-sim's flag set (verify against --help at build time)
        flag = "-u" if motion_fmt == "ecef" else "-x"
        argv = [self.binary, "-e", nav_file, flag, motion_file,
                "-T", start_time, "-d", str(int(duration_s)),
                "-s", str(int(sample_rate)), "-b", str(int(iq_bits)),
                "-o", out_file]
        if iono:
            argv.append("-i")
        return argv
