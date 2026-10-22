import math

_R = 6_371_000.0          # mean earth radius, metres
_A = 6_378_137.0          # WGS-84 semi-major axis
_F = 1 / 298.257223563    # WGS-84 flattening
_E2 = _F * (2 - _F)

def haversine_m(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return _R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

def interpolate(lat1, lng1, lat2, lng2, frac):
    return (lat1 + (lat2 - lat1) * frac, lng1 + (lng2 - lng1) * frac)

def bearing_deg(lat1, lng1, lat2, lng2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lng2 - lng1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

def lla_to_ecef(lat, lng, alt_m):
    phi, lmb = math.radians(lat), math.radians(lng)
    n = _A / math.sqrt(1 - _E2 * math.sin(phi) ** 2)
    x = (n + alt_m) * math.cos(phi) * math.cos(lmb)
    y = (n + alt_m) * math.cos(phi) * math.sin(lmb)
    z = (n * (1 - _E2) + alt_m) * math.sin(phi)
    return (x, y, z)
