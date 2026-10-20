from ..core.models import Constellation
from .gps_sdr_sim import GpsSdrSim
from .galileo_sdr_sim import GalileoSdrSim
from .glonass import GlonassBackend
from .beidou import BeidouBackend

def build_registry(config) -> dict:
    """config.resolve_tool(key) -> binary path/name. Keys: gps, galileo, gnss_multi."""
    gnss_multi = config.resolve_tool("gnss_multi")
    return {
        Constellation.GPS: GpsSdrSim(config.resolve_tool("gps")),
        Constellation.GALILEO: GalileoSdrSim(config.resolve_tool("galileo")),
        Constellation.GLONASS: GlonassBackend(gnss_multi),
        Constellation.BEIDOU: BeidouBackend(gnss_multi),
    }
