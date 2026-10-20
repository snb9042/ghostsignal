from .glonass import GlonassBackend
from ..core.models import Constellation
from ..constants import BEIDOU_B1_HZ

class BeidouBackend(GlonassBackend):
    name = "gnss-multi (beidou)"
    constellation = Constellation.BEIDOU
    default_freq_hz = BEIDOU_B1_HZ
    constellation_flag = "beidou"
