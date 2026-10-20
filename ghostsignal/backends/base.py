from __future__ import annotations
import shutil, os
from abc import ABC, abstractmethod
from ..core.models import Constellation

class SignalGenerator(ABC):
    name: str = "generator"
    constellation: Constellation = Constellation.GPS
    default_freq_hz: int = 1_575_420_000
    supported_motion_formats: set[str] = {"llh", "ecef"}

    def __init__(self, binary: str):
        self.binary = binary

    def available(self) -> bool:
        return bool(shutil.which(self.binary)) or os.path.isfile(self.binary)

    @abstractmethod
    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file) -> list[str]:
        ...
