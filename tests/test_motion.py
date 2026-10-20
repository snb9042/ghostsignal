# tests/test_motion.py
from ghostsignal.core import motion
from ghostsignal.core.models import Route, Waypoint, SpeedProfile

def _line_route(km):
    # east-west line of approx `km` length near equator
    deg = km / 111.195
    return Route([Waypoint(0.0, 0.0), Waypoint(0.0, deg)], None, km, "straight")

def test_constant_trajectory_point_count_and_timing():
    r = _line_route(1.0)                     # 1 km
    sp = SpeedProfile("constant", 3.6)       # 3.6 km/h = 1 m/s -> 1000 s
    traj = motion.build_trajectory(r, sp, hz=10)
    assert traj[0].t_s == 0.0
    assert abs(traj[-1].t_s - 1000.0) < 1.0  # ~1000 s at 1 m/s over 1 km
    assert abs((traj[1].t_s - traj[0].t_s) - 0.1) < 1e-9

def test_constant_trajectory_moves_monotonically_east():
    r = _line_route(1.0)
    traj = motion.build_trajectory(r, SpeedProfile("constant", 36.0), hz=10)
    lngs = [p.lng for p in traj]
    assert lngs == sorted(lngs)
    assert traj[0].lng == 0.0

def test_trapezoidal_reaches_endpoint():
    r = _line_route(2.0)
    sp = SpeedProfile("trapezoidal", 72.0, accel_ms2=2.0, decel_ms2=2.0)
    traj = motion.build_trajectory(r, sp, hz=10)
    assert abs(traj[-1].lng - (2.0 / 111.195)) < 1e-4

def test_llh_csv_format():
    r = _line_route(0.1)
    traj = motion.build_trajectory(r, SpeedProfile("constant", 36.0), hz=10)
    line0 = motion.to_llh_csv(traj).splitlines()[0]
    parts = [p.strip() for p in line0.split(",")]
    assert parts[0] == "0.0" and len(parts) == 4

def test_nmea_gga_has_checksum_and_prefix():
    r = _line_route(0.1)
    traj = motion.build_trajectory(r, SpeedProfile("constant", 36.0), hz=10)
    first = motion.to_nmea_gga(traj, "2026-10-19T12:00:00Z").splitlines()[0]
    assert first.startswith("$GPGGA,")
    assert "*" in first and len(first.split("*")[1]) == 2

def test_chunking_respects_cap():
    r = _line_route(10.0)
    sp = SpeedProfile("constant", 36.0)      # 10 m/s -> 1000 s
    traj = motion.build_trajectory(r, sp, hz=10)
    chunks = motion.chunk_trajectory(traj, cap_s=300)
    assert all((c[-1].t_s - c[0].t_s) <= 300.0 + 1e-6 for c in chunks)
    assert sum(len(c) for c in chunks) == len(traj)
