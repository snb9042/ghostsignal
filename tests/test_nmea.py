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
