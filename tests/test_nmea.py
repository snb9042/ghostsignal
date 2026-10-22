import pytest
from ghostsignal.core import nmea

SAMPLE = """$GPGGA,120000.00,4206.0000,N,02319.0000,E,1,08,0.9,100.0,M,0.0,M,,*5C
$GPRMC,120000.00,A,4206.0000,N,02319.0000,E,0.0,0.0,191026,,,A*6A
$GPGGA,120001.00,4206.0600,N,02319.0000,E,1,08,0.9,100.0,M,0.0,M,,*5A
"""

def test_parse_two_fixes():
    r = nmea.parse_nmea_track(SAMPLE)
    assert r.source == "nmea"
    assert len(r.waypoints) == 2
    assert abs(r.waypoints[0].lat - 42.1) < 1e-6
    assert abs(r.waypoints[0].lng - 23.3166667) < 1e-4
    assert r.geometry["type"] == "LineString"
    assert r.distance_km > 0

def test_parse_rejects_empty():
    with pytest.raises(ValueError):
        nmea.parse_nmea_track("not a fix\n")


def test_parse_skips_corrupt_line():
    """Parse track with one garbage GGA line skipped, two valid ones kept."""
    track = """$GPGGA,120000.00,4206.0000,N,02319.0000,E,1,08,0.9,100.0,M,0.0,M,,*5C
$GPGGA,120001.00,invalid,N,02319.0000,E,1,08,0.9,100.0,M,0.0,M,,*5A
$GPGGA,120002.00,4206.1000,N,02319.0000,E,1,08,0.9,100.0,M,0.0,M,,*5B
"""
    r = nmea.parse_nmea_track(track)
    assert len(r.waypoints) == 2
    assert r.source == "nmea"


def test_parse_all_garbage_raises():
    """Parse track with only a garbage line still raises ValueError."""
    track = """$GPGGA,120000.00,invalid,N,02319.0000,E,1,08,0.9,100.0,M,0.0,M,,*5C
"""
    with pytest.raises(ValueError):
        nmea.parse_nmea_track(track)
