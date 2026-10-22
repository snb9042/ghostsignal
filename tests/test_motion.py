# tests/test_motion.py
import random
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

def test_trapezoidal_zero_cruise_terminates():
    r = _line_route(0.05)   # 50 m
    sp = SpeedProfile("trapezoidal", 0.0, accel_ms2=1.0, decel_ms2=1.0)
    traj = motion.build_trajectory(r, sp, hz=10)
    assert 0 < len(traj) < 100000        # bounded -> loop terminated
    assert traj[-1].t_s >= traj[0].t_s

def test_nmea_timestamps_resolve_subsecond():
    r = _line_route(0.1)
    traj = motion.build_trajectory(r, SpeedProfile("constant", 36.0), hz=10)
    lines = motion.to_nmea_gga(traj, "2026-10-19T12:00:00Z").splitlines()
    stamps = [ln.split(",")[1] for ln in lines[:10]]   # t=0.0..0.9
    assert len(set(stamps)) == len(stamps)             # all distinct

def test_randomise_reaches_end_and_varies():
    from ghostsignal.core.geo import haversine_m
    r = _line_route(2.0)
    sp = SpeedProfile("constant", 60.0, randomise=True, variance_pct=30)
    traj = motion.build_trajectory(r, sp, hz=10, rng=random.Random(42))
    assert abs(traj[-1].lng - (2.0 / 111.195)) < 1e-3          # still reaches endpoint
    gaps = [haversine_m(traj[i].lat, traj[i].lng, traj[i+1].lat, traj[i+1].lng)
            for i in range(min(60, len(traj) - 1))]
    assert max(gaps) - min(gaps) > 1e-6                        # non-uniform spacing (speed varied)

def test_randomise_deterministic_with_seed():
    r = _line_route(1.0)
    sp = SpeedProfile("constant", 60.0, randomise=True, variance_pct=30)
    a = motion.build_trajectory(r, sp, hz=10, rng=random.Random(7))
    b = motion.build_trajectory(r, sp, hz=10, rng=random.Random(7))
    assert [(p.lat, p.lng) for p in a] == [(p.lat, p.lng) for p in b]

def test_non_randomise_unchanged():
    # constant, no randomise -> uniform spacing (regression guard)
    from ghostsignal.core.geo import haversine_m
    r = _line_route(1.0)
    traj = motion.build_trajectory(r, SpeedProfile("constant", 36.0), hz=10)
    gaps = [haversine_m(traj[i].lat, traj[i].lng, traj[i+1].lat, traj[i+1].lng)
            for i in range(5, min(40, len(traj) - 1))]
    assert max(gaps) - min(gaps) < 1e-3                        # essentially uniform
