from __future__ import annotations
import enum
from dataclasses import dataclass, field, asdict

class Constellation(enum.Enum):
    GPS = "gps"
    GALILEO = "galileo"
    GLONASS = "glonass"
    BEIDOU = "beidou"

@dataclass
class Waypoint:
    lat: float
    lng: float
    alt: float = 100.0
    def to_dict(self): return {"lat": self.lat, "lng": self.lng, "alt": self.alt}
    @classmethod
    def from_dict(cls, d): return cls(d["lat"], d["lng"], d.get("alt", 100.0))

@dataclass
class Route:
    waypoints: list[Waypoint]
    geometry: dict | None
    distance_km: float
    source: str
    def to_dict(self):
        return {"waypoints": [w.to_dict() for w in self.waypoints],
                "geometry": self.geometry, "distance_km": self.distance_km,
                "source": self.source}
    @classmethod
    def from_dict(cls, d):
        return cls([Waypoint.from_dict(w) for w in d["waypoints"]],
                   d.get("geometry"), d["distance_km"], d["source"])

@dataclass
class TrajectoryPoint:
    t_s: float
    lat: float
    lng: float
    alt: float

@dataclass
class SpeedProfile:
    kind: str                       # "constant" | "trapezoidal"
    cruise_kmh: float
    accel_ms2: float | None = None
    decel_ms2: float | None = None
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**d)

@dataclass
class SdrConfig:
    device: str
    constellation: Constellation
    freq_hz: int
    sample_rate_hz: int
    tx_gain_db: int
    iq_bits: int = 8
    enable_iono: bool = False
    def to_dict(self):
        d = asdict(self); d["constellation"] = self.constellation.value; return d
    @classmethod
    def from_dict(cls, d):
        d = dict(d); d["constellation"] = Constellation(d["constellation"]); return cls(**d)

@dataclass
class Session:
    name: str
    transport: str
    speed_profile: SpeedProfile
    start_time_utc: str
    waypoints: list[Waypoint]
    sdr: SdrConfig
    planner_only: bool = True
    schema: str = "2"
    def to_dict(self):
        return {"name": self.name, "transport": self.transport,
                "speed_profile": self.speed_profile.to_dict(),
                "start_time_utc": self.start_time_utc,
                "waypoints": [w.to_dict() for w in self.waypoints],
                "sdr": self.sdr.to_dict(), "planner_only": self.planner_only,
                "schema": self.schema}
    @classmethod
    def from_dict(cls, d):
        return cls(name=d["name"], transport=d["transport"],
                   speed_profile=SpeedProfile.from_dict(d["speed_profile"]),
                   start_time_utc=d["start_time_utc"],
                   waypoints=[Waypoint.from_dict(w) for w in d["waypoints"]],
                   sdr=SdrConfig.from_dict(d["sdr"]),
                   planner_only=d.get("planner_only", True),
                   schema=d.get("schema", "2"))
