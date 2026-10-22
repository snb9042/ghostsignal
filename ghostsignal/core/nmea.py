from __future__ import annotations
from .models import Waypoint, Route
from .geo import haversine_m

def _coord(raw: str, hemi: str, deg_digits: int) -> float:
    deg = float(raw[:deg_digits])
    minutes = float(raw[deg_digits:])
    val = deg + minutes / 60.0
    return -val if hemi in ("S", "W") else val

def parse_nmea_track(text: str) -> Route:
    wps: list[Waypoint] = []
    for line in text.splitlines():
        line = line.strip()
        if not (line.startswith("$GPGGA") or line.startswith("$GNGGA")):
            continue
        f = line.split("*")[0].split(",")
        if len(f) < 10 or not f[2] or not f[4]:
            continue
        # Skip if hemisphere fields are empty (malformed)
        if not f[3] or not f[5]:
            continue
        try:
            lat = _coord(f[2], f[3], 2)
            lng = _coord(f[4], f[5], 3)
            alt = float(f[9]) if f[9] else 100.0
        except ValueError:
            # Skip line with corrupt (present but non-numeric) field
            continue
        wps.append(Waypoint(lat, lng, alt))
    if not wps:
        raise ValueError("no valid $..GGA fixes found")
    dist_m = sum(haversine_m(wps[i].lat, wps[i].lng, wps[i+1].lat, wps[i+1].lng)
                 for i in range(len(wps) - 1))
    geom = {"type": "LineString", "coordinates": [[w.lng, w.lat] for w in wps]}
    return Route(wps, geom, dist_m / 1000.0, "nmea")
