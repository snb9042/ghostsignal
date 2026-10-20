from __future__ import annotations
import datetime as dt
from .models import Route, SpeedProfile, TrajectoryPoint
from .geo import haversine_m, interpolate, lla_to_ecef
from ..constants import MOTION_HZ, USER_MOTION_CAP_S

def route_polyline(route: Route):
    if route.geometry and route.geometry.get("coordinates"):
        alt = route.waypoints[0].alt if route.waypoints else 100.0
        return [(c[1], c[0], alt) for c in route.geometry["coordinates"]]
    return [(w.lat, w.lng, w.alt) for w in route.waypoints]

def _segment_lengths(poly):
    segs = []
    for i in range(len(poly) - 1):
        segs.append(haversine_m(poly[i][0], poly[i][1], poly[i + 1][0], poly[i + 1][1]))
    return segs

def _speed_at(d, total, sp: SpeedProfile):
    """Return instantaneous speed (m/s) at distance d along a total-length path."""
    cruise = sp.cruise_kmh / 3.6
    if sp.kind != "trapezoidal" or not sp.accel_ms2:
        return max(cruise, 0.1)
    a, de = sp.accel_ms2, (sp.decel_ms2 or sp.accel_ms2)
    d_acc = cruise ** 2 / (2 * a)
    d_dec = cruise ** 2 / (2 * de)
    if d_acc + d_dec > total:                   # triangular: never reach cruise
        d_acc = total * de / (a + de)
        d_dec = total - d_acc
    if d < d_acc:
        return max((2 * a * d) ** 0.5, 0.1)
    if d > total - d_dec:
        return max((2 * de * max(total - d, 0)) ** 0.5, 0.1)
    return max(cruise, 0.1)

def build_trajectory(route: Route, sp: SpeedProfile, hz: int = MOTION_HZ):
    poly = route_polyline(route)
    if len(poly) < 2:
        p = poly[0] if poly else (0.0, 0.0, 100.0)
        return [TrajectoryPoint(0.0, p[0], p[1], p[2])]
    segs = _segment_lengths(poly)
    total = sum(segs)
    dt_step = 1.0 / hz
    traj, t, d = [], 0.0, 0.0
    while d <= total + 1e-6:
        # locate d on the polyline
        acc, idx = 0.0, 0
        while idx < len(segs) and acc + segs[idx] < d:
            acc += segs[idx]; idx += 1
        if idx >= len(segs):
            lat, lng, alt = poly[-1]
        else:
            frac = (d - acc) / segs[idx] if segs[idx] else 0.0
            lat, lng = interpolate(poly[idx][0], poly[idx][1], poly[idx + 1][0], poly[idx + 1][1], frac)
            alt = poly[idx][2] + (poly[idx + 1][2] - poly[idx][2]) * frac
        traj.append(TrajectoryPoint(round(t, 3), lat, lng, alt))
        v = _speed_at(d, total, sp)
        d += v * dt_step
        t += dt_step
    return traj

def to_llh_csv(traj) -> str:
    return "\n".join(f"{p.t_s:.1f}, {p.lat:.9f}, {p.lng:.9f}, {p.alt:.3f}" for p in traj)

def to_ecef_csv(traj) -> str:
    out = []
    for p in traj:
        x, y, z = lla_to_ecef(p.lat, p.lng, p.alt)
        out.append(f"{p.t_s:.1f},{x:.3f},{y:.3f},{z:.3f}")
    return "\n".join(out)

def _nmea_checksum(body: str) -> str:
    cs = 0
    for ch in body:
        cs ^= ord(ch)
    return f"{cs:02X}"

def _dm(value: float, is_lat: bool):
    hemi = ("N" if value >= 0 else "S") if is_lat else ("E" if value >= 0 else "W")
    value = abs(value)
    deg = int(value)
    minutes = (value - deg) * 60
    width = 2 if is_lat else 3
    return f"{deg:0{width}d}{minutes:07.4f}", hemi

def to_nmea_gga(traj, start_utc: str) -> str:
    base = dt.datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
    lines = []
    for p in traj:
        _t = base + dt.timedelta(seconds=p.t_s)
        tstamp = _t.strftime("%H%M%S") + f".{_t.microsecond // 10000:02d}"
        lat_s, ns = _dm(p.lat, True)
        lng_s, ew = _dm(p.lng, False)
        body = f"GPGGA,{tstamp},{lat_s},{ns},{lng_s},{ew},1,08,0.9,{p.alt:.1f},M,0.0,M,,"
        lines.append(f"${body}*{_nmea_checksum(body)}")
    return "\n".join(lines)

def chunk_trajectory(traj, cap_s: float = USER_MOTION_CAP_S):
    if not traj:
        return []
    chunks, cur, start_t = [], [], traj[0].t_s
    for p in traj:
        if p.t_s - start_t > cap_s and cur:
            chunks.append(cur); cur = []; start_t = p.t_s
        cur.append(p)
    if cur:
        chunks.append(cur)
    return chunks
