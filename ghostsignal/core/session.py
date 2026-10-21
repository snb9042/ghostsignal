from __future__ import annotations
import json
from pathlib import Path
from .models import Session, Waypoint, SpeedProfile, SdrConfig, Constellation

_DEVICES = {0: "HackRF One", 1: "LimeSDR"}

def save_session(session: Session, path: str) -> None:
    Path(path).write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")

def _migrate_v1(d: dict) -> Session:
    freq = d.get("freq_mhz")
    if freq is not None:
        freq_hz = int(round(freq * 1e6))
    else:
        raw = d.get("freq", 1_575_420_000)
        freq_hz = int(raw) if raw > 100000 else int(round(raw * 1e6))
    start = d.get("start_time", "2026-01-01T00:00:00")
    if not start.endswith("Z") and "+" not in start:
        start = start + "Z"
    sdr = SdrConfig(device=_DEVICES.get(d.get("device", 0), "HackRF One"),
                    constellation=Constellation.GPS, freq_hz=freq_hz,
                    sample_rate_hz=int(d.get("sample_rate", 2_600_000)),
                    tx_gain_db=int(d.get("gain", 30)), iq_bits=8)
    return Session(name=d.get("name", "Session"),
                   transport=d.get("transport", "drive"),
                   speed_profile=SpeedProfile("constant", float(d.get("speed_kmh", 60))),
                   start_time_utc=start,
                   waypoints=[Waypoint.from_dict(w) for w in d.get("waypoints", [])],
                   sdr=sdr, planner_only=True, schema="2")

def load_session(path: str) -> Session:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema") == "2":
        return Session.from_dict(d)
    return _migrate_v1(d)
