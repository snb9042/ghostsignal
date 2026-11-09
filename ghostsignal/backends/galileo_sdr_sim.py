from .base import SignalGenerator
from ..core.models import Constellation
from ..constants import GALILEO_E1_HZ


class GalileoSdrSim(SignalGenerator):
    """Galileo E1B/C backend — wraps harshadms/galileo-sdr-sim's ``usrp_galileo``.

    The real CLI differs from gps-sdr-sim: it uses ``-U 1`` to disable the USRP
    (so it writes a file sink), ``-b 1`` to disable the bit stream, ``-o`` for
    the IQ file, and continuous motion via ``-x`` (a ``time, lat, lon, height``
    10 Hz file — the same format GhostSignal generates for GPS, enabled by a
    local patch adding ``-x`` user-motion support). Only llh motion is
    supported. NOTE: the IQ output is 16-bit interleaved short, so transmitting
    it via HackRF (8-bit) needs a sample-format conversion step.
    """
    name = "galileo-sdr-sim"
    constellation = Constellation.GALILEO
    default_freq_hz = GALILEO_E1_HZ
    supported_motion_formats = {"llh"}

    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file):
        # usrp_galileo file-sink, continuous-motion mode.
        # -U 1 / -b 1 carry a dummy "1" value (getopt consumes it; the flag just
        # disables USRP / bit-stream). Duration comes from the motion file.
        return [self.binary,
                "-e", nav_file,
                "-x", motion_file,
                "-o", out_file,
                "-T", start_time,
                "-U", "1",
                "-b", "1"]
