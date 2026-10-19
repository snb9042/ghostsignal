import datetime as dt
from ghostsignal.core.models import (
    Waypoint, Constellation, SpeedProfile, SdrConfig, Session,
)

def test_waypoint_roundtrip():
    w = Waypoint(42.1, 23.2, 150.0)
    assert Waypoint.from_dict(w.to_dict()) == w

def test_waypoint_default_alt():
    assert Waypoint(1.0, 2.0).alt == 100.0

def test_constellation_value():
    assert Constellation.GALILEO.value == "galileo"

def test_sdrconfig_roundtrip_serialises_constellation_as_string():
    c = SdrConfig("HackRF One", Constellation.GPS, 1_575_420_000, 2_600_000, 30)
    d = c.to_dict()
    assert d["constellation"] == "gps"
    assert SdrConfig.from_dict(d) == c

def test_session_roundtrip():
    s = Session(
        name="S1", transport="drive",
        speed_profile=SpeedProfile("constant", 60.0),
        start_time_utc="2026-10-19T12:00:00Z",
        waypoints=[Waypoint(42.1, 23.2), Waypoint(42.2, 23.3)],
        sdr=SdrConfig("HackRF One", Constellation.GPS, 1_575_420_000, 2_600_000, 30),
    )
    assert Session.from_dict(s.to_dict()) == s
    assert s.schema == "2"
