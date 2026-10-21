from __future__ import annotations
import os
from pathlib import Path

_ENV = {"gps": "GPS_SDR_SIM", "galileo": "GALILEO_SDR_SIM",
        "gnss_multi": "GNSS_MULTI_SIM", "hackrf": "HACKRF_TRANSFER",
        "soapy": "SOAPY_SDR_UTIL"}
_BARE = {"gps": "gps-sdr-sim", "galileo": "galileo-sdr-sim",
         "gnss_multi": "gnss-sim", "hackrf": "hackrf_transfer",
         "soapy": "SoapySDRUtil"}
DEFAULT_TOOL_KEYS = {"gps", "galileo", "gnss_multi", "hackrf", "soapy"}
_WIN_DIRS = [r"C:\Program Files\PothosSDR\bin"]

class ToolConfig:
    def __init__(self, overrides: dict | None = None):
        self.overrides = dict(overrides or {})

    def resolve_tool(self, key: str) -> str:
        if key in self.overrides:
            return self.overrides[key]
        env = _ENV.get(key)
        if env and os.environ.get(env):
            return os.environ[env]
        bare = _BARE.get(key, key)
        for d in _WIN_DIRS:
            cand = Path(d) / (bare + ".exe")
            if cand.is_file():
                return str(cand)
        return bare

def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    p = Path(base) / "GhostSignal" / "ephemeris"
    return str(p)
