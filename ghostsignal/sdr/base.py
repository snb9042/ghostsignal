from __future__ import annotations
import shutil, os
from abc import ABC, abstractmethod

class SdrTransmitter(ABC):
    name: str = "sdr"
    def __init__(self, binary: str):
        self.binary = binary
    def available(self) -> bool:
        return bool(shutil.which(self.binary)) or os.path.isfile(self.binary)
    @abstractmethod
    def build_argv(self, *, iq_file, freq_hz, sample_rate, gain_db) -> list[str]:
        ...
