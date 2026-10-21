import json
from ghostsignal.core.session import save_session, load_session
from ghostsignal.core.models import Session, Waypoint, SpeedProfile, SdrConfig, Constellation

def test_v2_roundtrip(tmp_path):
    s = Session("S", "drive", SpeedProfile("constant", 60.0), "2026-10-19T12:00:00Z",
                [Waypoint(42.0, 23.0)], SdrConfig("HackRF One", Constellation.GPS,
                1_575_420_000, 2_600_000, 30))
    p = tmp_path / "s.json"
    save_session(s, str(p))
    assert load_session(str(p)) == s

def test_v1_migration(tmp_path):
    v1 = {"name": "Old", "transport": "cycle", "speed_kmh": 15,
          "start_time": "2026-03-27T19:00:00", "waypoints": [{"lat": 42.6, "lng": 23.3}],
          "freq_mhz": 1575.42, "gain": 25, "sample_rate": 2_600_000, "device": 0}
    p = tmp_path / "old.json"
    p.write_text(json.dumps(v1))
    s = load_session(str(p))
    assert s.schema == "2"
    assert s.transport == "cycle"
    assert s.sdr.freq_hz == 1_575_420_000
    assert s.sdr.tx_gain_db == 25
    assert s.sdr.device == "HackRF One"
    assert s.waypoints[0].lat == 42.6

def test_v1_migration_freq_in_hz(tmp_path):
    v1 = {"name": "Old", "transport": "drive", "speed_kmh": 60,
          "start_time": "2026-03-27T19:00:00", "waypoints": [{"lat": 1, "lng": 2}],
          "freq": 1_227_600_000, "gain": 30, "sample_rate": 2_600_000, "device": 1}
    p = tmp_path / "old2.json"
    p.write_text(json.dumps(v1))
    s = load_session(str(p))
    assert s.sdr.freq_hz == 1_227_600_000
    assert s.sdr.device == "LimeSDR"
