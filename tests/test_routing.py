from ghostsignal.core import routing
from ghostsignal.core.models import Waypoint

WPS = [Waypoint(42.0, 23.0), Waypoint(42.0, 23.1)]

def test_osrm_url_lng_lat_order():
    url = routing.osrm_url(WPS, "driving")
    assert "/driving/23.0,42.0;23.1,42.0" in url
    assert "overview=full" in url and "geometries=geojson" in url

def test_build_route_uses_fetch_for_road_profile():
    fake = {"routes": [{"distance": 8450.0,
                        "geometry": {"type": "LineString", "coordinates": [[23.0, 42.0], [23.1, 42.0]]}}]}
    r = routing.build_route(WPS, "drive", fetch=lambda u: fake)
    assert r.source == "osrm"
    assert abs(r.distance_km - 8.45) < 1e-9
    assert r.geometry["type"] == "LineString"

def test_build_route_straight_line_for_plane():
    r = routing.build_route(WPS, "plane", fetch=lambda u: (_ for _ in ()).throw(AssertionError("must not fetch")))
    assert r.source == "straight"
    assert r.geometry is None
    assert r.distance_km > 0

def test_build_route_falls_back_to_straight_on_fetch_error():
    def boom(url): raise OSError("network down")
    r = routing.build_route(WPS, "drive", fetch=boom)
    assert r.source == "straight"
