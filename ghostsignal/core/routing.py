from __future__ import annotations
import json, urllib.request
from .models import Waypoint, Route
from .geo import haversine_m
from ..constants import OSRM_PROFILES

class RoutingError(Exception):
    pass

def urlopen_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())

def osrm_url(waypoints: list[Waypoint], profile: str) -> str:
    coords = ";".join(f"{w.lng},{w.lat}" for w in waypoints)
    return (f"https://router.project-osrm.org/route/v1/{profile}/{coords}"
            f"?overview=full&geometries=geojson")

def _straight(waypoints: list[Waypoint]) -> Route:
    dist_m = sum(haversine_m(waypoints[i].lat, waypoints[i].lng,
                             waypoints[i + 1].lat, waypoints[i + 1].lng)
                 for i in range(len(waypoints) - 1))
    return Route(waypoints, None, dist_m / 1000.0, "straight")

def build_route(waypoints, transport, fetch=urlopen_json) -> Route:
    if len(waypoints) < 2:
        return Route(list(waypoints), None, 0.0, "straight")
    profile = OSRM_PROFILES.get(transport)
    if profile is None:
        return _straight(waypoints)
    try:
        data = fetch(osrm_url(waypoints, profile))
        route = data["routes"][0]
        return Route(list(waypoints), route["geometry"],
                     route["distance"] / 1000.0, "osrm")
    except Exception:
        return _straight(waypoints)
