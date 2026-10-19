import math
from ghostsignal.core import geo

def test_haversine_known_distance():
    # ~111.19 km per degree of latitude at the equator
    d = geo.haversine_m(0.0, 0.0, 1.0, 0.0)
    assert abs(d - 111_195) < 200

def test_haversine_zero():
    assert geo.haversine_m(42.0, 23.0, 42.0, 23.0) == 0.0

def test_interpolate_midpoint():
    lat, lng = geo.interpolate(0.0, 0.0, 10.0, 20.0, 0.5)
    assert abs(lat - 5.0) < 1e-9 and abs(lng - 10.0) < 1e-9

def test_bearing_north():
    assert abs(geo.bearing_deg(0, 0, 1, 0) - 0.0) < 1e-6

def test_bearing_east():
    assert abs(geo.bearing_deg(0, 0, 0, 1) - 90.0) < 1e-6

def test_lla_to_ecef_equator_prime_meridian():
    x, y, z = geo.lla_to_ecef(0.0, 0.0, 0.0)
    assert abs(x - 6_378_137.0) < 1.0 and abs(y) < 1e-6 and abs(z) < 1e-6
