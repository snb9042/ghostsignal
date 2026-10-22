# GhostSignal v2 Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild GhostSignal as a modular, tested PyQt6 app that actually drives the SDR end-to-end, produces continuous moving-fix GNSS playback, and supports multiple constellations via a pluggable backend seam.

**Architecture:** A pure, Qt-free `core/` package holds all logic (geo, routing, motion, NMEA, CLI building, session, RINEX) and is unit-tested without a display. `backends/` and `sdr/` wrap external simulator/transmitter binaries behind ABCs. `pipeline.py` orchestrates generate→transmit. A thin Qt layer (`ui/`, `workers/`) imports core, never the reverse. `headless/` reuses core for a GUI-less CLI.

**Tech Stack:** Python 3.12, PyQt6 + PyQt6-WebEngine, Leaflet (in-page JS), `gps-sdr-sim` / `galileo-sdr-sim` (C sims), `hackrf_transfer` / SoapySDR, pytest. Windows-primary.

**Spec:** `docs/superpowers/specs/2026-10-19-ghostsignal-v2-rebuild-design.md`

## Global Constraints

- **Python 3.12 venv** — PyQt6 has no 3.14 wheels; all commands assume the 3.12 venv is active.
- **No PyQt6 import** anywhere under `ghostsignal/core`, `ghostsignal/backends`, `ghostsignal/sdr`, `ghostsignal/headless` (enforced by a test).
- **HackRF I/Q is 8-bit** — the HackRF generation path must pass `-b 8` to the sim.
- **Agent does not run pytest on this machine** (user constraint) — at each "run the test" step, the executor requests the user run the suite and reports back, OR runs it only if the user has explicitly authorized it this session. Test *commands* are written assuming an active 3.12 venv.
- **Version string:** `__version__ = "2.0.0"`; window title `GhostSignal v2.0.0 — GNSS Signal Simulator`.
- **License:** MIT, unchanged. Keep the legal/authorization notice prominent in README and UI.
- **Commit after every task** on branch `rebuild/v2`. Commit messages end with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- **Line endings:** repo is on Windows; let git handle LF/CRLF (already warned). Write files with `\n`.
- **Tool paths** resolve in this order: explicit config/QSettings → env var (`GPS_SDR_SIM`, `GALILEO_SDR_SIM`, `GNSS_MULTI_SIM`, `HACKRF_TRANSFER`, `SOAPY_SDR_UTIL`) → PATH → known install dirs (`C:\Program Files\PothosSDR\bin`).

---

## File Structure

```
pyproject.toml                         # package metadata, deps, entry points
ghostsignal/__init__.py                # __version__
ghostsignal/__main__.py                # python -m ghostsignal → GUI
ghostsignal/app.py                     # QApplication bootstrap + theme
ghostsignal/constants.py               # freqs, speeds, OSRM profiles, constellations
ghostsignal/config.py                  # tool-path resolution + settings
ghostsignal/core/geo.py                # haversine, lla<->ecef, interpolation, bearing
ghostsignal/core/models.py             # dataclasses
ghostsignal/core/routing.py            # OSRM + straight-line
ghostsignal/core/motion.py             # trajectory generation + motion-file writers
ghostsignal/core/nmea.py               # NMEA GGA track parsing
ghostsignal/core/cli.py                # argv + bash-script builders
ghostsignal/core/session.py            # Session JSON + v1 migration
ghostsignal/core/rinex.py              # ephemeris download/cache/decompress
ghostsignal/backends/base.py           # SignalGenerator ABC
ghostsignal/backends/registry.py       # backend discovery
ghostsignal/backends/gps_sdr_sim.py    # GPS (real)
ghostsignal/backends/galileo_sdr_sim.py# Galileo (real)
ghostsignal/backends/glonass.py        # GLONASS (external multi-GNSS)
ghostsignal/backends/beidou.py         # BeiDou (external multi-GNSS)
ghostsignal/sdr/base.py                # SdrTransmitter ABC
ghostsignal/sdr/hackrf.py              # hackrf_transfer
ghostsignal/sdr/limesdr.py             # SoapySDR
ghostsignal/pipeline.py                # generate→transmit orchestrator
ghostsignal/ui/*.py                    # main_window, panels, bridge, dialogs, widgets
ghostsignal/ui/assets/map.html         # Leaflet document
ghostsignal/ui/assets/style.qss        # dark theme
ghostsignal/workers/*.py               # osrm, pipeline, playback QThreads
ghostsignal/headless/cli.py            # ghostsignal-cli
tests/test_*.py                        # pytest (pure core + dry-run)
scripts/*.ps1                          # venv + sim build scripts
Dockerfile / docker-compose.yml        # headless generation image
```

All tests go in `tests/` at repo root. The legacy `ghostsignal.py` stays in git history (v1) and is removed in the final task once v2 reaches parity.

---

## Task 1: Project scaffold & packaging

**Files:**
- Create: `pyproject.toml`, `ghostsignal/__init__.py`, `ghostsignal/constants.py`, `ghostsignal/__main__.py`
- Create: `ghostsignal/core/__init__.py`, `ghostsignal/backends/__init__.py`, `ghostsignal/sdr/__init__.py`, `ghostsignal/ui/__init__.py`, `ghostsignal/workers/__init__.py`, `ghostsignal/headless/__init__.py`
- Create: `scripts/setup-venv.ps1`
- Test: `tests/test_architecture.py`, `tests/test_constants.py`

**Interfaces:**
- Produces: `ghostsignal.__version__: str`; `ghostsignal.constants` module with `GPS_L1_HZ`, `GALILEO_E1_HZ`, `GLONASS_L1_HZ`, `BEIDOU_B1_HZ` (int Hz), `TRANSPORT_SPEEDS: dict[str,int]`, `OSRM_PROFILES: dict[str,str|None]`, `SAMPLE_RATES: tuple[int,...]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_constants.py
from ghostsignal import constants, __version__

def test_version():
    assert __version__ == "2.0.0"

def test_gnss_frequencies_hz():
    assert constants.GPS_L1_HZ == 1_575_420_000
    assert constants.GALILEO_E1_HZ == 1_575_420_000
    assert constants.GLONASS_L1_HZ == 1_602_000_000
    assert constants.BEIDOU_B1_HZ == 1_561_098_000

def test_transport_speeds():
    assert constants.TRANSPORT_SPEEDS["drive"] == 60
    assert set(constants.TRANSPORT_SPEEDS) == {"walk", "cycle", "drive", "boat", "plane"}
```

```python
# tests/test_architecture.py
import pathlib, re

PURE = ["core", "backends", "sdr", "headless"]

def test_no_pyqt_in_pure_packages():
    root = pathlib.Path(__file__).resolve().parent.parent / "ghostsignal"
    offenders = []
    for pkg in PURE:
        for py in (root / pkg).rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            if re.search(r"^\s*(import|from)\s+PyQt6", text, re.M):
                offenders.append(str(py))
    assert offenders == [], f"PyQt6 imported in pure packages: {offenders}"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_constants.py tests/test_architecture.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ghostsignal'`.

- [ ] **Step 3: Write minimal implementation**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "ghostsignal"
version = "2.0.0"
description = "GNSS signal simulation & SDR transmission GUI for authorized testing"
requires-python = ">=3.12"
license = { text = "MIT" }
dependencies = ["PyQt6>=6.6.0", "PyQt6-WebEngine>=6.6.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
ghostsignal-cli = "ghostsignal.headless.cli:main"

[project.gui-scripts]
ghostsignal = "ghostsignal.app:main"

[tool.setuptools.packages.find]
include = ["ghostsignal*"]

[tool.setuptools.package-data]
"ghostsignal.ui" = ["assets/*"]
```

```python
# ghostsignal/__init__.py
__version__ = "2.0.0"
```

```python
# ghostsignal/constants.py
GPS_L1_HZ = 1_575_420_000
GPS_L2_HZ = 1_227_600_000
GPS_L5_HZ = 1_176_450_000
GALILEO_E1_HZ = 1_575_420_000
GLONASS_L1_HZ = 1_602_000_000
BEIDOU_B1_HZ = 1_561_098_000

TRANSPORT_SPEEDS = {"walk": 5, "cycle": 15, "drive": 60, "boat": 25, "plane": 800}
OSRM_PROFILES = {"walk": "foot", "cycle": "cycling", "drive": "driving",
                 "boat": None, "plane": None}
SAMPLE_RATES = (1_000_000, 2_600_000, 4_000_000, 8_000_000)
MOTION_HZ = 10
USER_MOTION_CAP_S = 300
```

Create empty `__init__.py` in each package dir (`ghostsignal/`, `core/`, `backends/`, `sdr/`, `ui/`, `workers/`, `headless/` — the top-level one already holds the version).

```python
# ghostsignal/__main__.py
from ghostsignal.app import main
if __name__ == "__main__":
    main()
```

```powershell
# scripts/setup-venv.ps1
param([string]$Py = "py -3.12")
Write-Host "Creating .venv with $Py ..."
Invoke-Expression "$Py -m venv .venv"
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Write-Host "Done. Activate with: .\.venv\Scripts\Activate.ps1"
```

- [ ] **Step 4: Install the package editable, run tests to verify they pass**

Run: `python -m pip install -e ".[dev]"` then `python -m pytest tests/test_constants.py tests/test_architecture.py -v`
Expected: PASS (both files).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml ghostsignal scripts tests/test_constants.py tests/test_architecture.py
git commit -m "feat: scaffold ghostsignal v2 package + constants + architecture test"
```

---

## Task 2: Geodesy helpers (`core/geo.py`)

**Files:**
- Create: `ghostsignal/core/geo.py`
- Test: `tests/test_geo.py`

**Interfaces:**
- Produces:
  - `haversine_m(lat1, lng1, lat2, lng2) -> float` (metres)
  - `interpolate(lat1, lng1, lat2, lng2, frac) -> tuple[float, float]` (linear in lat/lng; frac 0..1)
  - `bearing_deg(lat1, lng1, lat2, lng2) -> float` (0..360)
  - `lla_to_ecef(lat, lng, alt_m) -> tuple[float, float, float]` (WGS-84, metres)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_geo.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_geo.py -v`
Expected: FAIL — `ModuleNotFoundError` / `AttributeError`.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/core/geo.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_geo.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/core/geo.py tests/test_geo.py
git commit -m "feat: add geodesy helpers (haversine, interpolate, bearing, lla->ecef)"
```

---

## Task 3: Data models (`core/models.py`)

**Files:**
- Create: `ghostsignal/core/models.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces (all `@dataclass`, all with `to_dict()` / `from_dict(d)` classmethods):
  - `Waypoint(lat: float, lng: float, alt: float = 100.0)`
  - `Constellation(enum.Enum)` — members `GPS`, `GALILEO`, `GLONASS`, `BEIDOU`; `.value` is lowercase name.
  - `Route(waypoints: list[Waypoint], geometry: dict | None, distance_km: float, source: str)`
  - `TrajectoryPoint(t_s: float, lat: float, lng: float, alt: float)`
  - `SpeedProfile(kind: str, cruise_kmh: float, accel_ms2: float | None = None, decel_ms2: float | None = None)` — `kind` ∈ {`"constant"`, `"trapezoidal"`}
  - `SdrConfig(device: str, constellation: Constellation, freq_hz: int, sample_rate_hz: int, tx_gain_db: int, iq_bits: int = 8, enable_iono: bool = False)`
  - `Session(name, transport, speed_profile, start_time_utc, waypoints, sdr, planner_only=True, schema="2")`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_models.py
import datetime as dt
from ghostsignal.core.models import (
    Waypoint, Constellation, SpeedProfile, SdrConfig, Session,
)

def test_waypoint_roundtrip():
    w = Waypoint(42.1, 23.2, 150.0)
    assert Waypoint.from_dict(w.to_dict()) == w

def test_waypoint_default_alt():
    assert Waypoint(1.0, 2.0).alt == 100.0

def test_constellation_value():
    assert Constellation.GALILEO.value == "galileo"

def test_sdrconfig_roundtrip_serialises_constellation_as_string():
    c = SdrConfig("HackRF One", Constellation.GPS, 1_575_420_000, 2_600_000, 30)
    d = c.to_dict()
    assert d["constellation"] == "gps"
    assert SdrConfig.from_dict(d) == c

def test_session_roundtrip():
    s = Session(
        name="S1", transport="drive",
        speed_profile=SpeedProfile("constant", 60.0),
        start_time_utc="2026-10-19T12:00:00Z",
        waypoints=[Waypoint(42.1, 23.2), Waypoint(42.2, 23.3)],
        sdr=SdrConfig("HackRF One", Constellation.GPS, 1_575_420_000, 2_600_000, 30),
    )
    assert Session.from_dict(s.to_dict()) == s
    assert s.schema == "2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_models.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/core/models.py
from __future__ import annotations
import enum
from dataclasses import dataclass, field, asdict

class Constellation(enum.Enum):
    GPS = "gps"
    GALILEO = "galileo"
    GLONASS = "glonass"
    BEIDOU = "beidou"

@dataclass
class Waypoint:
    lat: float
    lng: float
    alt: float = 100.0
    def to_dict(self): return {"lat": self.lat, "lng": self.lng, "alt": self.alt}
    @classmethod
    def from_dict(cls, d): return cls(d["lat"], d["lng"], d.get("alt", 100.0))

@dataclass
class Route:
    waypoints: list[Waypoint]
    geometry: dict | None
    distance_km: float
    source: str
    def to_dict(self):
        return {"waypoints": [w.to_dict() for w in self.waypoints],
                "geometry": self.geometry, "distance_km": self.distance_km,
                "source": self.source}
    @classmethod
    def from_dict(cls, d):
        return cls([Waypoint.from_dict(w) for w in d["waypoints"]],
                   d.get("geometry"), d["distance_km"], d["source"])

@dataclass
class TrajectoryPoint:
    t_s: float
    lat: float
    lng: float
    alt: float

@dataclass
class SpeedProfile:
    kind: str                       # "constant" | "trapezoidal"
    cruise_kmh: float
    accel_ms2: float | None = None
    decel_ms2: float | None = None
    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, d): return cls(**d)

@dataclass
class SdrConfig:
    device: str
    constellation: Constellation
    freq_hz: int
    sample_rate_hz: int
    tx_gain_db: int
    iq_bits: int = 8
    enable_iono: bool = False
    def to_dict(self):
        d = asdict(self); d["constellation"] = self.constellation.value; return d
    @classmethod
    def from_dict(cls, d):
        d = dict(d); d["constellation"] = Constellation(d["constellation"]); return cls(**d)

@dataclass
class Session:
    name: str
    transport: str
    speed_profile: SpeedProfile
    start_time_utc: str
    waypoints: list[Waypoint]
    sdr: SdrConfig
    planner_only: bool = True
    schema: str = "2"
    def to_dict(self):
        return {"name": self.name, "transport": self.transport,
                "speed_profile": self.speed_profile.to_dict(),
                "start_time_utc": self.start_time_utc,
                "waypoints": [w.to_dict() for w in self.waypoints],
                "sdr": self.sdr.to_dict(), "planner_only": self.planner_only,
                "schema": self.schema}
    @classmethod
    def from_dict(cls, d):
        return cls(name=d["name"], transport=d["transport"],
                   speed_profile=SpeedProfile.from_dict(d["speed_profile"]),
                   start_time_utc=d["start_time_utc"],
                   waypoints=[Waypoint.from_dict(w) for w in d["waypoints"]],
                   sdr=SdrConfig.from_dict(d["sdr"]),
                   planner_only=d.get("planner_only", True),
                   schema=d.get("schema", "2"))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_models.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/core/models.py tests/test_models.py
git commit -m "feat: add core data models with JSON round-trip"
```

---

## Task 4: Routing (`core/routing.py`)

**Files:**
- Create: `ghostsignal/core/routing.py`
- Test: `tests/test_routing.py`

**Interfaces:**
- Consumes: `models.Waypoint`, `models.Route`, `geo.haversine_m`, `constants.OSRM_PROFILES`.
- Produces:
  - `build_route(waypoints, transport, fetch=urlopen_json) -> Route` — uses OSRM for road profiles; straight-line (great-circle sum) when the profile is `None` (boat/plane) or when `fetch` raises. `fetch(url) -> dict` is injectable for tests.
  - `osrm_url(waypoints, profile) -> str`
  - exception `RoutingError`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_routing.py
import pytest
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_routing.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/core/routing.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_routing.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/core/routing.py tests/test_routing.py
git commit -m "feat: add routing (OSRM + straight-line fallback) with injectable fetch"
```

---

## Task 5: Motion & trajectory (`core/motion.py`)

**Files:**
- Create: `ghostsignal/core/motion.py`
- Test: `tests/test_motion.py`

**Interfaces:**
- Consumes: `models.Route`, `models.SpeedProfile`, `models.TrajectoryPoint`, `geo.haversine_m`, `geo.interpolate`, `geo.lla_to_ecef`, `constants.MOTION_HZ`, `constants.USER_MOTION_CAP_S`.
- Produces:
  - `route_polyline(route) -> list[tuple[float,float,float]]` — ordered (lat,lng,alt); uses `route.geometry` coords when present (GeoJSON is lng,lat), else the waypoints.
  - `build_trajectory(route, speed_profile, hz=MOTION_HZ) -> list[TrajectoryPoint]`
  - `to_llh_csv(traj) -> str` — lines `"{t:.1f}, {lat:.9f}, {lng:.9f}, {alt:.3f}"` (gps-sdr-sim `-x`)
  - `to_ecef_csv(traj) -> str` — lines `"{t:.1f},{x:.3f},{y:.3f},{z:.3f}"` (`-u`)
  - `to_nmea_gga(traj, start_utc) -> str` — `$GPGGA` sentences with checksum
  - `chunk_trajectory(traj, cap_s=USER_MOTION_CAP_S) -> list[list[TrajectoryPoint]]`

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_motion.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/core/motion.py
from __future__ import annotations
import datetime as dt
from .models import Route, SpeedProfile, TrajectoryPoint, Waypoint
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
    return cruise

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
        tstamp = (base + dt.timedelta(seconds=p.t_s)).strftime("%H%M%S.00")
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_motion.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/core/motion.py tests/test_motion.py
git commit -m "feat: add trajectory generation, speed profiles, motion-file writers, chunking"
```

---

## Task 6: NMEA replay parsing (`core/nmea.py`)

**Files:**
- Create: `ghostsignal/core/nmea.py`
- Test: `tests/test_nmea.py`

**Interfaces:**
- Consumes: `models.Waypoint`, `models.Route`.
- Produces: `parse_nmea_track(text: str) -> Route` — extracts `$GPGGA`/`$GNGGA` fixes into a `Route(source="nmea")`; `distance_km` summed via haversine; `geometry` is a GeoJSON LineString. Raises `ValueError` if no valid fix.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_nmea.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_nmea.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/core/nmea.py
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
        lat = _coord(f[2], f[3], 2)
        lng = _coord(f[4], f[5], 3)
        alt = float(f[9]) if f[9] else 100.0
        wps.append(Waypoint(lat, lng, alt))
    if not wps:
        raise ValueError("no valid $..GGA fixes found")
    dist_m = sum(haversine_m(wps[i].lat, wps[i].lng, wps[i+1].lat, wps[i+1].lng)
                 for i in range(len(wps) - 1))
    geom = {"type": "LineString", "coordinates": [[w.lng, w.lat] for w in wps]}
    return Route(wps, geom, dist_m / 1000.0, "nmea")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_nmea.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/core/nmea.py tests/test_nmea.py
git commit -m "feat: add NMEA GGA track parsing for replay"
```

---

## Task 7: Signal-generator backends (`backends/`)

**Files:**
- Create: `ghostsignal/backends/base.py`, `gps_sdr_sim.py`, `galileo_sdr_sim.py`, `glonass.py`, `beidou.py`, `registry.py`
- Test: `tests/test_backends.py`

**Interfaces:**
- Consumes: `models.Constellation`, `config.resolve_tool(name)` (Task 12 provides the real one; here backends take an explicit `binary` path so they are testable in isolation), `constants` frequencies.
- Produces:
  - `SignalGenerator` ABC with: `name: str`, `constellation: Constellation`, `default_freq_hz: int`, `supported_motion_formats: set[str]`, `binary: str`, `available() -> bool`, `build_argv(*, nav_file, motion_file, motion_fmt, start_time, duration_s, sample_rate, iq_bits, iono, out_file) -> list[str]`.
  - `GpsSdrSim`, `GalileoSdrSim`, `GlonassBackend`, `BeidouBackend` (last two wrap a multi-GNSS tool and set a `constellation_flag`).
  - `registry.build_registry(config) -> dict[Constellation, SignalGenerator]`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_backends.py
import shutil
from ghostsignal.backends.gps_sdr_sim import GpsSdrSim
from ghostsignal.backends.galileo_sdr_sim import GalileoSdrSim
from ghostsignal.backends.glonass import GlonassBackend
from ghostsignal.core.models import Constellation

def test_gps_argv_uses_llh_motion_and_8bit():
    gps = GpsSdrSim(binary="gps-sdr-sim")
    argv = gps.build_argv(nav_file="brdc.nav", motion_file="m.csv", motion_fmt="llh",
                          start_time="2026/10/19,12:00:00", duration_s=120,
                          sample_rate=2_600_000, iq_bits=8, iono=False, out_file="o.bin")
    assert argv[0] == "gps-sdr-sim"
    assert "-e" in argv and "brdc.nav" in argv
    assert "-x" in argv and "m.csv" in argv       # llh motion → -x
    assert argv[argv.index("-b") + 1] == "8"
    assert argv[argv.index("-s") + 1] == "2600000"

def test_gps_ecef_motion_uses_u_flag():
    gps = GpsSdrSim(binary="gps-sdr-sim")
    argv = gps.build_argv(nav_file="n", motion_file="m", motion_fmt="ecef",
                          start_time="2026/10/19,12:00:00", duration_s=10,
                          sample_rate=2_600_000, iq_bits=8, iono=True, out_file="o")
    assert "-u" in argv and "-x" not in argv
    assert "-i" in argv                            # iono enabled

def test_galileo_default_freq_is_e1():
    assert GalileoSdrSim(binary="x").default_freq_hz == 1_575_420_000
    assert GalileoSdrSim(binary="x").constellation is Constellation.GALILEO

def test_available_false_when_binary_missing():
    assert GpsSdrSim(binary="definitely-not-a-real-binary-xyz").available() is False

def test_glonass_argv_includes_constellation_selector():
    g = GlonassBackend(binary="gnss-sim")
    argv = g.build_argv(nav_file="n", motion_file="m", motion_fmt="llh",
                        start_time="2026/10/19,12:00:00", duration_s=10,
                        sample_rate=2_600_000, iq_bits=8, iono=False, out_file="o")
    assert "glonass" in " ".join(argv).lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_backends.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/backends/base.py
from __future__ import annotations
import shutil, os
from abc import ABC, abstractmethod
from ..core.models import Constellation

class SignalGenerator(ABC):
    name: str = "generator"
    constellation: Constellation = Constellation.GPS
    default_freq_hz: int = 1_575_420_000
    supported_motion_formats: set[str] = {"llh", "ecef"}

    def __init__(self, binary: str):
        self.binary = binary

    def available(self) -> bool:
        return bool(shutil.which(self.binary)) or os.path.isfile(self.binary)

    @abstractmethod
    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file) -> list[str]:
        ...
```

```python
# ghostsignal/backends/gps_sdr_sim.py
from .base import SignalGenerator
from ..core.models import Constellation
from ..constants import GPS_L1_HZ

_FMT_FLAG = {"llh": "-x", "ecef": "-u", "nmea": "-g"}

class GpsSdrSim(SignalGenerator):
    name = "gps-sdr-sim"
    constellation = Constellation.GPS
    default_freq_hz = GPS_L1_HZ
    supported_motion_formats = {"llh", "ecef", "nmea"}

    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file):
        argv = [self.binary, "-e", nav_file,
                _FMT_FLAG[motion_fmt], motion_file,
                "-T", start_time, "-d", str(int(duration_s)),
                "-s", str(int(sample_rate)), "-b", str(int(iq_bits)),
                "-o", out_file]
        if iono:
            argv.append("-i")
        return argv
```

```python
# ghostsignal/backends/galileo_sdr_sim.py
from .base import SignalGenerator
from ..core.models import Constellation
from ..constants import GALILEO_E1_HZ

class GalileoSdrSim(SignalGenerator):
    name = "galileo-sdr-sim"
    constellation = Constellation.GALILEO
    default_freq_hz = GALILEO_E1_HZ
    supported_motion_formats = {"llh", "ecef"}

    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file):
        # galileo-sdr-sim mirrors gps-sdr-sim's flag set (verify against --help at build time)
        flag = "-u" if motion_fmt == "ecef" else "-x"
        argv = [self.binary, "-e", nav_file, flag, motion_file,
                "-T", start_time, "-d", str(int(duration_s)),
                "-s", str(int(sample_rate)), "-b", str(int(iq_bits)),
                "-o", out_file]
        if iono:
            argv.append("-i")
        return argv
```

```python
# ghostsignal/backends/glonass.py
from .base import SignalGenerator
from ..core.models import Constellation
from ..constants import GLONASS_L1_HZ

class GlonassBackend(SignalGenerator):
    """Wraps a configurable multi-GNSS simulator (default: gnss-signal-simulator-rs).
    Experimental: available() only true when the user has configured a working binary."""
    name = "gnss-multi (glonass)"
    constellation = Constellation.GLONASS
    default_freq_hz = GLONASS_L1_HZ
    constellation_flag = "glonass"
    supported_motion_formats = {"llh"}

    def build_argv(self, *, nav_file, motion_file, motion_fmt, start_time,
                   duration_s, sample_rate, iq_bits, iono, out_file):
        return [self.binary, "--system", self.constellation_flag,
                "--ephemeris", nav_file, "--motion", motion_file,
                "--start", start_time, "--duration", str(int(duration_s)),
                "--sample-rate", str(int(sample_rate)), "--bits", str(int(iq_bits)),
                "--output", out_file]
```

```python
# ghostsignal/backends/beidou.py
from .glonass import GlonassBackend
from ..core.models import Constellation
from ..constants import BEIDOU_B1_HZ

class BeidouBackend(GlonassBackend):
    name = "gnss-multi (beidou)"
    constellation = Constellation.BEIDOU
    default_freq_hz = BEIDOU_B1_HZ
    constellation_flag = "beidou"
```

```python
# ghostsignal/backends/registry.py
from ..core.models import Constellation
from .gps_sdr_sim import GpsSdrSim
from .galileo_sdr_sim import GalileoSdrSim
from .glonass import GlonassBackend
from .beidou import BeidouBackend

def build_registry(config) -> dict:
    """config.resolve_tool(key) -> binary path/name. Keys: gps, galileo, gnss_multi."""
    gnss_multi = config.resolve_tool("gnss_multi")
    return {
        Constellation.GPS: GpsSdrSim(config.resolve_tool("gps")),
        Constellation.GALILEO: GalileoSdrSim(config.resolve_tool("galileo")),
        Constellation.GLONASS: GlonassBackend(gnss_multi),
        Constellation.BEIDOU: BeidouBackend(gnss_multi),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_backends.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/backends tests/test_backends.py
git commit -m "feat: add pluggable signal-generator backends (GPS/Galileo real, GLONASS/BeiDou external)"
```

---

## Task 8: SDR transmitters (`sdr/`)

**Files:**
- Create: `ghostsignal/sdr/base.py`, `hackrf.py`, `limesdr.py`
- Test: `tests/test_sdr.py`

**Interfaces:**
- Produces:
  - `SdrTransmitter` ABC: `name: str`, `binary: str`, `available() -> bool`, `build_argv(*, iq_file, freq_hz, sample_rate, gain_db) -> list[str]`.
  - `HackRfTransmitter`, `LimeSdrTransmitter`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sdr.py
from ghostsignal.sdr.hackrf import HackRfTransmitter
from ghostsignal.sdr.limesdr import LimeSdrTransmitter

def test_hackrf_argv():
    tx = HackRfTransmitter(binary="hackrf_transfer")
    argv = tx.build_argv(iq_file="o.bin", freq_hz=1_575_420_000,
                         sample_rate=2_600_000, gain_db=30)
    assert argv[0] == "hackrf_transfer"
    assert argv[argv.index("-t") + 1] == "o.bin"
    assert argv[argv.index("-f") + 1] == "1575420000"
    assert argv[argv.index("-s") + 1] == "2600000"
    assert argv[argv.index("-x") + 1] == "30"
    assert "-a" in argv and "-R" in argv          # amp on, repeat

def test_lime_argv_has_tx_direction():
    tx = LimeSdrTransmitter(binary="SoapySDRUtil")
    argv = tx.build_argv(iq_file="o.bin", freq_hz=1_575_420_000,
                        sample_rate=2_600_000, gain_db=30)
    joined = " ".join(argv)
    assert "driver=lime" in joined and "TX" in joined
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sdr.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/sdr/base.py
from __future__ import annotations
import shutil, os
from abc import ABC, abstractmethod

class SdrTransmitter(ABC):
    name: str = "sdr"
    def __init__(self, binary: str):
        self.binary = binary
    def available(self) -> bool:
        return bool(shutil.which(self.binary)) or os.path.isfile(self.binary)
    @abstractmethod
    def build_argv(self, *, iq_file, freq_hz, sample_rate, gain_db) -> list[str]:
        ...
```

```python
# ghostsignal/sdr/hackrf.py
from .base import SdrTransmitter

class HackRfTransmitter(SdrTransmitter):
    name = "HackRF One"
    def build_argv(self, *, iq_file, freq_hz, sample_rate, gain_db):
        return [self.binary, "-t", iq_file, "-f", str(int(freq_hz)),
                "-s", str(int(sample_rate)), "-a", "1", "-x", str(int(gain_db)), "-R"]
```

```python
# ghostsignal/sdr/limesdr.py
from .base import SdrTransmitter

class LimeSdrTransmitter(SdrTransmitter):
    name = "LimeSDR"
    def build_argv(self, *, iq_file, freq_hz, sample_rate, gain_db):
        return [self.binary, '--args=driver=lime', "--direction=TX", "--chan=0",
                f"--freq={int(freq_hz)}", f"--rate={int(sample_rate)}",
                f"--gain={int(gain_db)}", f"--file={iq_file}"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_sdr.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/sdr tests/test_sdr.py
git commit -m "feat: add SDR transmitter wrappers (HackRF, LimeSDR)"
```

---

## Task 9: CLI script builder (`core/cli.py`)

**Files:**
- Create: `ghostsignal/core/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: a `SignalGenerator` and `SdrTransmitter` (duck-typed: anything with `build_argv`), `models.SdrConfig`.
- Produces: `build_script(*, generator, transmitter, nav_file, motion_file, motion_fmt, start_time, duration_s, sdr: SdrConfig, planner_note: bool) -> str` — a `#!/bin/bash` script with a generate step and a transmit step built from the backends' `build_argv`, quoting args that contain spaces.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli.py
from ghostsignal.core.cli import build_script
from ghostsignal.core.models import SdrConfig, Constellation
from ghostsignal.backends.gps_sdr_sim import GpsSdrSim
from ghostsignal.sdr.hackrf import HackRfTransmitter

def _script():
    sdr = SdrConfig("HackRF One", Constellation.GPS, 1_575_420_000, 2_600_000, 30, iq_bits=8)
    return build_script(generator=GpsSdrSim("gps-sdr-sim"),
                        transmitter=HackRfTransmitter("hackrf_transfer"),
                        nav_file="brdc.nav", motion_file="motion.csv", motion_fmt="llh",
                        start_time="2026/10/19,12:00:00", duration_s=120,
                        sdr=sdr, planner_note=True)

def test_script_has_both_steps():
    s = _script()
    assert s.startswith("#!/bin/bash")
    assert "gps-sdr-sim -e brdc.nav -x motion.csv" in s
    assert "hackrf_transfer -t gps_sim.bin -f 1575420000" in s
    assert "-b 8" in s

def test_script_quotes_spaces():
    from ghostsignal.sdr.limesdr import LimeSdrTransmitter
    from ghostsignal.core.cli import build_script
    sdr = SdrConfig("LimeSDR", Constellation.GPS, 1_575_420_000, 2_600_000, 30)
    s = build_script(generator=GpsSdrSim("/path with space/gps-sdr-sim"),
                     transmitter=LimeSdrTransmitter("SoapySDRUtil"),
                     nav_file="n", motion_file="m", motion_fmt="llh",
                     start_time="t", duration_s=10, sdr=sdr, planner_note=False)
    assert "'/path with space/gps-sdr-sim'" in s
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/core/cli.py
from __future__ import annotations
import shlex

OUT_BIN = "gps_sim.bin"

def _fmt(argv) -> str:
    return " ".join(shlex.quote(a) if (" " in a) else a for a in argv)

def build_script(*, generator, transmitter, nav_file, motion_file, motion_fmt,
                 start_time, duration_s, sdr, planner_note: bool) -> str:
    gen_argv = generator.build_argv(
        nav_file=nav_file, motion_file=motion_file, motion_fmt=motion_fmt,
        start_time=start_time, duration_s=duration_s,
        sample_rate=sdr.sample_rate_hz, iq_bits=sdr.iq_bits,
        iono=sdr.enable_iono, out_file=OUT_BIN)
    tx_argv = transmitter.build_argv(
        iq_file=OUT_BIN, freq_hz=sdr.freq_hz,
        sample_rate=sdr.sample_rate_hz, gain_db=sdr.tx_gain_db)
    lines = [
        "#!/bin/bash",
        "# GhostSignal v2 — auto-generated GNSS simulation script",
        f"# Constellation: {sdr.constellation.value}  Device: {sdr.device}",
        "set -e",
        "",
        "# Step 1: generate GNSS baseband I/Q (continuous motion file)",
        _fmt(gen_argv),
        "",
        "# Step 2: transmit",
        _fmt(tx_argv),
    ]
    if planner_note:
        lines += ["", "# NOTE: transmit only in an authorized, shielded environment."]
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/core/cli.py tests/test_cli.py
git commit -m "feat: add CLI script builder from backend argv"
```

---

## Task 10: Session persistence + v1 migration (`core/session.py`)

**Files:**
- Create: `ghostsignal/core/session.py`
- Test: `tests/test_session.py`

**Interfaces:**
- Consumes: `models.Session`, `models.Waypoint`, `models.SpeedProfile`, `models.SdrConfig`, `models.Constellation`.
- Produces:
  - `save_session(session: Session, path: str) -> None`
  - `load_session(path: str) -> Session` — detects v1 files (no `"schema"` key or `schema=="1"`) and migrates: v1 `freq` (Hz or MHz), `gain`, `device` index, `waypoints`, `transport`, `speed_kmh`, `start_time` → v2 `Session`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_session.py
import json
from ghostsignal.core.session import save_session, load_session
from ghostsignal.core.models import Session, Waypoint, SpeedProfile, SdrConfig, Constellation

def test_v2_roundtrip(tmp_path):
    s = Session("S", "drive", SpeedProfile("constant", 60.0), "2026-10-19T12:00:00Z",
                [Waypoint(42.0, 23.0)], SdrConfig("HackRF One", Constellation.GPS,
                1_575_420_000, 2_600_000, 30))
    p = tmp_path / "s.json"
    save_session(s, str(p))
    assert load_session(str(p)) == s

def test_v1_migration(tmp_path):
    v1 = {"name": "Old", "transport": "cycle", "speed_kmh": 15,
          "start_time": "2026-03-27T19:00:00", "waypoints": [{"lat": 42.6, "lng": 23.3}],
          "freq_mhz": 1575.42, "gain": 25, "sample_rate": 2_600_000, "device": 0}
    p = tmp_path / "old.json"
    p.write_text(json.dumps(v1))
    s = load_session(str(p))
    assert s.schema == "2"
    assert s.transport == "cycle"
    assert s.sdr.freq_hz == 1_575_420_000
    assert s.sdr.tx_gain_db == 25
    assert s.sdr.device == "HackRF One"
    assert s.waypoints[0].lat == 42.6

def test_v1_migration_freq_in_hz(tmp_path):
    v1 = {"name": "Old", "transport": "drive", "speed_kmh": 60,
          "start_time": "2026-03-27T19:00:00", "waypoints": [{"lat": 1, "lng": 2}],
          "freq": 1_227_600_000, "gain": 30, "sample_rate": 2_600_000, "device": 1}
    p = tmp_path / "old2.json"
    p.write_text(json.dumps(v1))
    s = load_session(str(p))
    assert s.sdr.freq_hz == 1_227_600_000
    assert s.sdr.device == "LimeSDR"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_session.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/core/session.py
from __future__ import annotations
import json
from pathlib import Path
from .models import Session, Waypoint, SpeedProfile, SdrConfig, Constellation

_DEVICES = {0: "HackRF One", 1: "LimeSDR"}

def save_session(session: Session, path: str) -> None:
    Path(path).write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")

def _migrate_v1(d: dict) -> Session:
    freq = d.get("freq_mhz")
    if freq is not None:
        freq_hz = int(round(freq * 1e6))
    else:
        raw = d.get("freq", 1_575_420_000)
        freq_hz = int(raw) if raw > 100000 else int(round(raw * 1e6))
    start = d.get("start_time", "2026-01-01T00:00:00")
    if not start.endswith("Z") and "+" not in start:
        start = start + "Z"
    sdr = SdrConfig(device=_DEVICES.get(d.get("device", 0), "HackRF One"),
                    constellation=Constellation.GPS, freq_hz=freq_hz,
                    sample_rate_hz=int(d.get("sample_rate", 2_600_000)),
                    tx_gain_db=int(d.get("gain", 30)), iq_bits=8)
    return Session(name=d.get("name", "Session"),
                   transport=d.get("transport", "drive"),
                   speed_profile=SpeedProfile("constant", float(d.get("speed_kmh", 60))),
                   start_time_utc=start,
                   waypoints=[Waypoint.from_dict(w) for w in d.get("waypoints", [])],
                   sdr=sdr, planner_only=True, schema="2")

def load_session(path: str) -> Session:
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    if d.get("schema") == "2":
        return Session.from_dict(d)
    return _migrate_v1(d)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_session.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/core/session.py tests/test_session.py
git commit -m "feat: add session persistence with v1->v2 migration"
```

---

## Task 11: Ephemeris / RINEX downloader (`core/rinex.py`)

**Files:**
- Create: `ghostsignal/core/rinex.py`
- Test: `tests/test_rinex.py`

**Interfaces:**
- Produces:
  - `brdc_filename(date: datetime.date) -> str` — `"brdc{DDD}0.{YY}n"` (day-of-year, 2-digit year).
  - `source_urls(date, sources: list[str]) -> list[str]` — candidate URLs, mirror order.
  - `ensure_ephemeris(date, cache_dir, sources=DEFAULT_SOURCES, fetch=..., opener=...) -> str` — returns a local `.nav` path; checks cache, else tries each URL via `fetch(url)->bytes`, decompresses `.gz`/`.Z`, writes to cache. Raises `EphemerisError` if all fail.
  - `decompress(name: str, data: bytes) -> bytes` — gunzip if `.gz`, else passthrough.
  - `DEFAULT_SOURCES: list[str]` (mirror identifiers), `EphemerisError`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rinex.py
import datetime, gzip, pytest
from ghostsignal.core import rinex

def test_brdc_filename_day_of_year():
    # 2026-01-01 is DOY 001
    assert rinex.brdc_filename(datetime.date(2026, 1, 1)) == "brdc0010.26n"

def test_brdc_filename_mid_year():
    d = datetime.date(2026, 3, 27)        # DOY 086
    assert rinex.brdc_filename(d) == "brdc0860.26n"

def test_decompress_gzip():
    raw = b"RINEX DATA"
    gz = gzip.compress(raw)
    assert rinex.decompress("brdc0010.26n.gz", gz) == raw

def test_ensure_uses_cache(tmp_path):
    cache = tmp_path
    (cache / "brdc0010.26n").write_bytes(b"CACHED")
    def fail(url): raise AssertionError("should not fetch")
    path = rinex.ensure_ephemeris(datetime.date(2026, 1, 1), str(cache), fetch=fail)
    assert path.endswith("brdc0010.26n")

def test_ensure_downloads_and_decompresses(tmp_path):
    import gzip
    payload = gzip.compress(b"NAVDATA")
    calls = []
    def fetch(url):
        calls.append(url)
        if url.endswith(".gz"):
            return payload
        raise OSError("404")
    path = rinex.ensure_ephemeris(datetime.date(2026, 1, 1), str(tmp_path), fetch=fetch)
    assert open(path, "rb").read() == b"NAVDATA"
    assert calls                                   # attempted at least one URL

def test_ensure_raises_when_all_fail(tmp_path):
    def fetch(url): raise OSError("down")
    with pytest.raises(rinex.EphemerisError):
        rinex.ensure_ephemeris(datetime.date(2026, 1, 1), str(tmp_path), fetch=fetch)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_rinex.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/core/rinex.py
from __future__ import annotations
import datetime, gzip, urllib.request
from pathlib import Path

class EphemerisError(Exception):
    pass

# Mirror bases. CDDIS needs Earthdata auth; BKG/IGS mirrors are no-auth.
DEFAULT_SOURCES = [
    "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/{yyyy}/{ddd}/",
    "https://cddis.nasa.gov/archive/gnss/data/daily/{yyyy}/brdc/",
]

def brdc_filename(date: datetime.date) -> str:
    ddd = date.timetuple().tm_yday
    return f"brdc{ddd:03d}0.{date.strftime('%y')}n"

def source_urls(date: datetime.date, sources=DEFAULT_SOURCES) -> list[str]:
    name = brdc_filename(date)
    ddd = f"{date.timetuple().tm_yday:03d}"
    urls = []
    for base in sources:
        b = base.format(yyyy=date.year, ddd=ddd)
        urls.append(b + name + ".gz")
        urls.append(b + name)
    return urls

def decompress(name: str, data: bytes) -> bytes:
    if name.endswith(".gz"):
        return gzip.decompress(data)
    return data

def urlopen_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
        return r.read()

def ensure_ephemeris(date, cache_dir, sources=DEFAULT_SOURCES,
                     fetch=urlopen_bytes) -> str:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    name = brdc_filename(date)
    local = cache / name
    if local.is_file():
        return str(local)
    last_err = None
    for url in source_urls(date, sources):
        try:
            data = decompress(url.rsplit("/", 1)[-1], fetch(url))
            local.write_bytes(data)
            return str(local)
        except Exception as e:      # try next mirror
            last_err = e
    raise EphemerisError(f"could not fetch ephemeris for {date}: {last_err}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_rinex.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/core/rinex.py tests/test_rinex.py
git commit -m "feat: add RINEX ephemeris downloader with mirror fallback + cache"
```

---

## Task 12: Config / tool resolution (`config.py`)

**Files:**
- Create: `ghostsignal/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces:
  - `DEFAULT_TOOL_KEYS = {"gps","galileo","gnss_multi","hackrf","soapy"}`
  - `class ToolConfig` with `resolve_tool(key: str) -> str` — resolution order: explicit `overrides` dict → env var (`GPS_SDR_SIM` etc.) → bare command name (on PATH at run time) → known Windows install dir. Pure (no Qt). Env-var map: `gps→GPS_SDR_SIM`, `galileo→GALILEO_SDR_SIM`, `gnss_multi→GNSS_MULTI_SIM`, `hackrf→HACKRF_TRANSFER`, `soapy→SOAPY_SDR_UTIL`.
  - `cache_dir() -> str` — per-user ephemeris cache path (AppData on Windows).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from ghostsignal.config import ToolConfig

def test_override_wins(monkeypatch):
    c = ToolConfig(overrides={"gps": "/custom/gps-sdr-sim"})
    assert c.resolve_tool("gps") == "/custom/gps-sdr-sim"

def test_env_var_used(monkeypatch):
    monkeypatch.setenv("HACKRF_TRANSFER", "/env/hackrf_transfer")
    c = ToolConfig()
    assert c.resolve_tool("hackrf") == "/env/hackrf_transfer"

def test_default_bare_command(monkeypatch):
    monkeypatch.delenv("GPS_SDR_SIM", raising=False)
    c = ToolConfig()
    assert c.resolve_tool("gps") == "gps-sdr-sim"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/config.py
from __future__ import annotations
import os
from pathlib import Path

_ENV = {"gps": "GPS_SDR_SIM", "galileo": "GALILEO_SDR_SIM",
        "gnss_multi": "GNSS_MULTI_SIM", "hackrf": "HACKRF_TRANSFER",
        "soapy": "SOAPY_SDR_UTIL"}
_BARE = {"gps": "gps-sdr-sim", "galileo": "galileo-sdr-sim",
         "gnss_multi": "gnss-sim", "hackrf": "hackrf_transfer",
         "soapy": "SoapySDRUtil"}
_WIN_DIRS = [r"C:\Program Files\PothosSDR\bin"]

class ToolConfig:
    def __init__(self, overrides: dict | None = None):
        self.overrides = dict(overrides or {})

    def resolve_tool(self, key: str) -> str:
        if key in self.overrides:
            return self.overrides[key]
        env = _ENV.get(key)
        if env and os.environ.get(env):
            return os.environ[env]
        bare = _BARE.get(key, key)
        for d in _WIN_DIRS:
            cand = Path(d) / (bare + ".exe")
            if cand.is_file():
                return str(cand)
        return bare

def cache_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    p = Path(base) / "GhostSignal" / "ephemeris"
    return str(p)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/config.py tests/test_config.py
git commit -m "feat: add tool-path resolution config"
```

---

## Task 13: Generate→transmit pipeline (`pipeline.py`)

**Files:**
- Create: `ghostsignal/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: a `SignalGenerator`, an `SdrTransmitter`, `models.SdrConfig`, a trajectory (list of `TrajectoryPoint`), `motion.to_llh_csv`.
- Produces:
  - `@dataclass PipelinePlan(gen_argv, tx_argv, motion_path, out_path, motion_text)`
  - `plan_pipeline(*, generator, transmitter, sdr, trajectory, nav_file, start_time, motion_fmt="llh", work_dir, motion_text=None) -> PipelinePlan` — pure; writes nothing; computes argv + intended file paths. `duration_s` is derived from `trajectory[-1].t_s`.
  - `run_pipeline(plan, *, writer, runner, on_event) -> int` — `writer(path, text)` persists the motion file; `runner(argv) -> int` executes a step; `on_event(stage, detail)` reports progress; returns final return code. Dry-run = pass a `runner` that records argv and returns 0.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pipeline.py
from ghostsignal import pipeline
from ghostsignal.core.models import SdrConfig, Constellation, TrajectoryPoint
from ghostsignal.backends.gps_sdr_sim import GpsSdrSim
from ghostsignal.sdr.hackrf import HackRfTransmitter

TRAJ = [TrajectoryPoint(0.0, 42.0, 23.0, 100.0),
        TrajectoryPoint(120.0, 42.1, 23.1, 100.0)]

def _plan(tmp):
    sdr = SdrConfig("HackRF One", Constellation.GPS, 1_575_420_000, 2_600_000, 30, iq_bits=8)
    return pipeline.plan_pipeline(generator=GpsSdrSim("gps-sdr-sim"),
                                  transmitter=HackRfTransmitter("hackrf_transfer"),
                                  sdr=sdr, trajectory=TRAJ, nav_file="brdc.nav",
                                  start_time="2026/10/19,12:00:00", work_dir=str(tmp))

def test_plan_duration_from_trajectory(tmp_path):
    plan = _plan(tmp_path)
    assert "-d" in plan.gen_argv
    assert plan.gen_argv[plan.gen_argv.index("-d") + 1] == "120"

def test_plan_argv_wiring(tmp_path):
    plan = _plan(tmp_path)
    assert plan.gen_argv[0] == "gps-sdr-sim"
    assert plan.tx_argv[0] == "hackrf_transfer"
    assert plan.out_path.endswith(".bin")
    assert "42.0" in plan.motion_text

def test_run_pipeline_dry_run_order(tmp_path):
    plan = _plan(tmp_path)
    ran, writes, events = [], [], []
    rc = pipeline.run_pipeline(plan,
                               writer=lambda p, t: writes.append(p),
                               runner=lambda argv: ran.append(argv) or 0,
                               on_event=lambda s, d: events.append(s))
    assert rc == 0
    assert ran[0][0] == "gps-sdr-sim" and ran[1][0] == "hackrf_transfer"
    assert writes == [plan.motion_path]
    assert "generate" in events and "transmit" in events

def test_run_pipeline_stops_if_generate_fails(tmp_path):
    plan = _plan(tmp_path)
    ran = []
    rc = pipeline.run_pipeline(plan, writer=lambda p, t: None,
                               runner=lambda argv: ran.append(argv) or (1 if len(ran) == 1 else 0),
                               on_event=lambda s, d: None)
    assert rc == 1
    assert len(ran) == 1               # transmit never runs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/pipeline.py
from __future__ import annotations
import os
from dataclasses import dataclass
from .core import motion as _motion

_FMT_WRITER = {"llh": _motion.to_llh_csv, "ecef": _motion.to_ecef_csv}

@dataclass
class PipelinePlan:
    gen_argv: list[str]
    tx_argv: list[str]
    motion_path: str
    out_path: str
    motion_text: str

def plan_pipeline(*, generator, transmitter, sdr, trajectory, nav_file,
                  start_time, motion_fmt="llh", work_dir, motion_text=None):
    duration_s = int(round(trajectory[-1].t_s)) if trajectory else 0
    motion_path = os.path.join(work_dir, "motion." + ("csv" if motion_fmt != "nmea" else "nmea"))
    out_path = os.path.join(work_dir, "gps_sim.bin")
    if motion_text is None:
        motion_text = _FMT_WRITER[motion_fmt](trajectory)
    gen_argv = generator.build_argv(
        nav_file=nav_file, motion_file=motion_path, motion_fmt=motion_fmt,
        start_time=start_time, duration_s=duration_s,
        sample_rate=sdr.sample_rate_hz, iq_bits=sdr.iq_bits,
        iono=sdr.enable_iono, out_file=out_path)
    tx_argv = transmitter.build_argv(
        iq_file=out_path, freq_hz=sdr.freq_hz,
        sample_rate=sdr.sample_rate_hz, gain_db=sdr.tx_gain_db)
    return PipelinePlan(gen_argv, tx_argv, motion_path, out_path, motion_text)

def run_pipeline(plan, *, writer, runner, on_event) -> int:
    on_event("motion", plan.motion_path)
    writer(plan.motion_path, plan.motion_text)
    on_event("generate", plan.gen_argv)
    rc = runner(plan.gen_argv)
    if rc != 0:
        on_event("error", f"generate exited {rc}")
        return rc
    on_event("transmit", plan.tx_argv)
    rc = runner(plan.tx_argv)
    on_event("done", rc)
    return rc
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pipeline.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/pipeline.py tests/test_pipeline.py
git commit -m "feat: add generate->transmit pipeline (pure plan + injectable runner)"
```

---

## Task 14: Headless CLI (`headless/cli.py`)

**Files:**
- Create: `ghostsignal/headless/cli.py`
- Test: `tests/test_headless.py`

**Interfaces:**
- Consumes: `session.load_session`, `routing.build_route`, `motion.build_trajectory`, `backends.registry.build_registry`, `sdr` transmitters, `pipeline`, `config.ToolConfig`.
- Produces: `main(argv: list[str] | None = None) -> int` with subcommand `run <session.json> [--dry-run] [--generate-only] [--nav FILE] [--work-dir DIR]`. In `--dry-run`, it prints the two argv lines and returns 0 without executing.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_headless.py
import json
from ghostsignal.headless.cli import main
from ghostsignal.core.models import Session, Waypoint, SpeedProfile, SdrConfig, Constellation
from ghostsignal.core.session import save_session

def _session_file(tmp_path):
    s = Session("S", "drive", SpeedProfile("constant", 60.0), "2026-10-19T12:00:00Z",
                [Waypoint(42.0, 23.0), Waypoint(42.05, 23.05)],
                SdrConfig("HackRF One", Constellation.GPS, 1_575_420_000, 2_600_000, 30))
    p = tmp_path / "s.json"; save_session(s, str(p)); return str(p)

def test_dry_run_prints_argv_and_returns_zero(tmp_path, capsys):
    sf = _session_file(tmp_path)
    rc = main(["run", sf, "--dry-run", "--nav", "brdc.nav", "--work-dir", str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "gps-sdr-sim" in out and "hackrf_transfer" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_headless.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/headless/cli.py
from __future__ import annotations
import argparse, subprocess, sys, shlex
from ..config import ToolConfig
from ..core.session import load_session
from ..core import routing, motion
from ..backends.registry import build_registry
from ..sdr.hackrf import HackRfTransmitter
from ..sdr.limesdr import LimeSdrTransmitter
from .. import pipeline

def _transmitter(cfg, device):
    if device == "LimeSDR":
        return LimeSdrTransmitter(cfg.resolve_tool("soapy"))
    return HackRfTransmitter(cfg.resolve_tool("hackrf"))

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ghostsignal-cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run")
    run.add_argument("session")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--generate-only", action="store_true")
    run.add_argument("--nav", default="brdc.nav")
    run.add_argument("--work-dir", default=".")
    args = ap.parse_args(argv)

    cfg = ToolConfig()
    s = load_session(args.session)
    route = routing.build_route(s.waypoints, s.transport)
    traj = motion.build_trajectory(route, s.speed_profile)
    registry = build_registry(cfg)
    gen = registry[s.sdr.constellation]
    tx = _transmitter(cfg, s.sdr.device)
    start_time = s.start_time_utc.replace("-", "/").replace("T", ",").replace("Z", "")
    plan = pipeline.plan_pipeline(generator=gen, transmitter=tx, sdr=s.sdr,
                                  trajectory=traj, nav_file=args.nav,
                                  start_time=start_time, work_dir=args.work_dir)
    if args.dry_run:
        print(" ".join(plan.gen_argv))
        print(" ".join(plan.tx_argv))
        return 0
    def writer(p, t): open(p, "w", encoding="utf-8").write(t)
    def runner(a):
        if args.generate_only and a is plan.tx_argv:
            return 0
        return subprocess.run(a).returncode
    return pipeline.run_pipeline(plan, writer=writer, runner=runner,
                                 on_event=lambda stage, d: print(f"[{stage}]", d))

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_headless.py -v`
Expected: PASS (1 test).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/headless/cli.py tests/test_headless.py
git commit -m "feat: add headless CLI (run session, dry-run, generate-only)"
```

---

## Task 15: UI assets (map + stylesheet)

**Files:**
- Create: `ghostsignal/ui/assets/map.html`, `ghostsignal/ui/assets/style.qss`
- Test: `tests/test_assets.py`

**Interfaces:**
- Produces: `map.html` (Leaflet + CartoDB dark tiles, `addMarker/clearMarkers/drawRoute/drawStraightLine/updatePosition/clearPosition` JS functions and a `pyBridge` click/drag hook — same API v1 used so the bridge is a drop-in), and `style.qss` (the v1 dark theme, moved out of the Python string).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_assets.py
import importlib.resources as res

def _read(name):
    return (res.files("ghostsignal.ui") / "assets" / name).read_text(encoding="utf-8")

def test_map_html_exposes_js_api():
    html = _read("map.html")
    for fn in ["function addMarker", "function clearMarkers", "function drawRoute",
               "function drawStraightLine", "function updatePosition", "function clearPosition"]:
        assert fn in html
    assert "pyBridge" in html

def test_style_qss_has_theme_colors():
    qss = _read("style.qss")
    assert "#00ffa3" in qss and "QPushButton" in qss
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_assets.py -v`
Expected: FAIL — files missing.

- [ ] **Step 3: Write the assets**

Create `ghostsignal/ui/assets/map.html` by copying the `MAP_HTML` body from v1 `ghostsignal.py` (lines ~288–382) verbatim — it already defines exactly these JS functions and the `pyBridge` hooks. Create `ghostsignal/ui/assets/style.qss` by copying the v1 `STYLE` string body (lines ~81–284) verbatim (strip the Python triple-quote wrapper). No logic changes; this task only relocates the two blobs into real asset files.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_assets.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/ui/assets tests/test_assets.py
git commit -m "feat: extract Leaflet map.html and dark style.qss into asset files"
```

---

## Task 16: Qt bridge + map panel (`ui/bridge.py`, `ui/map_panel.py`)

**Files:**
- Create: `ghostsignal/ui/bridge.py`, `ghostsignal/ui/map_panel.py`
- Test: `tests/test_ui_import.py` (import-only smoke, skipped if PyQt6 absent)

**Interfaces:**
- Consumes: `map.html` asset.
- Produces:
  - `MapBridge(QObject)` with signals `map_clicked(float,float)`, `marker_dragged(int,float,float)` and slots `onMapClick`, `onMarkerDragged`.
  - `MapPanel(QWidget)` wrapping a `QWebEngineView`, registering `pyBridge` via `QWebChannel`, loading `map.html` from assets with base URL `https://ghostsignal.local/`. Methods: `set_markers(waypoints)`, `draw_route(geometry)`, `draw_straight(waypoints)`, `update_position(lat,lng)`, `clear_position()`, `clear_all()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ui_import.py
import pytest
pytest.importorskip("PyQt6.QtWebEngineWidgets")

def test_bridge_and_map_panel_importable():
    from ghostsignal.ui.bridge import MapBridge
    from ghostsignal.ui import map_panel
    assert hasattr(MapBridge, "onMapClick")
    assert hasattr(map_panel, "MapPanel")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_ui_import.py -v`
Expected: FAIL (import error) or SKIP if PyQt6-WebEngine not installed. On the dev machine, install deps first so it runs: `python -m pip install -e .`.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/ui/bridge.py
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

class MapBridge(QObject):
    map_clicked = pyqtSignal(float, float)
    marker_dragged = pyqtSignal(int, float, float)

    @pyqtSlot(float, float)
    def onMapClick(self, lat, lng):
        self.map_clicked.emit(lat, lng)

    @pyqtSlot(int, float, float)
    def onMarkerDragged(self, idx, lat, lng):
        self.marker_dragged.emit(idx, lat, lng)
```

```python
# ghostsignal/ui/map_panel.py
import json, importlib.resources as res
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QUrl
from .bridge import MapBridge

def _map_html():
    return (res.files("ghostsignal.ui") / "assets" / "map.html").read_text(encoding="utf-8")

class MapPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.view = QWebEngineView()
        self.bridge = MapBridge(self)
        ch = QWebChannel(self.view.page())
        ch.registerObject("pyBridge", self.bridge)
        self.view.page().setWebChannel(ch)
        self.view.page().setHtml(_map_html(), QUrl("https://ghostsignal.local/"))
        lay.addWidget(self.view)

    def _js(self, code):
        self.view.page().runJavaScript(code)

    def set_markers(self, waypoints):
        n = len(waypoints)
        js = "clearMarkers();"
        for i, w in enumerate(waypoints):
            first = "true" if i == 0 else "false"
            last = "true" if (i == n - 1 and n > 1) else "false"
            js += f"addMarker({w.lat},{w.lng},{i},{first},{last});"
        self._js(js)

    def draw_route(self, geometry):
        self._js(f"drawRoute({json.dumps(geometry)});")

    def draw_straight(self, waypoints):
        pts = [{"lat": w.lat, "lng": w.lng} for w in waypoints]
        self._js(f"drawStraightLine({json.dumps(pts)});")

    def update_position(self, lat, lng):
        self._js(f"updatePosition({lat},{lng});")

    def clear_position(self):
        self._js("clearPosition();")

    def clear_all(self):
        self._js("clearMarkers(); if(routeLayer){routeLayer.remove();routeLayer=null;} clearPosition();")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_ui_import.py -v`
Expected: PASS (after `pip install -e .`).

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/ui/bridge.py ghostsignal/ui/map_panel.py tests/test_ui_import.py
git commit -m "feat: add Qt map bridge + MapPanel wrapping QWebEngineView"
```

---

## Task 17: Workers (`workers/`)

**Files:**
- Create: `ghostsignal/workers/osrm_worker.py`, `ghostsignal/workers/pipeline_worker.py`, `ghostsignal/workers/playback_worker.py`
- Test: `tests/test_workers_import.py`

**Interfaces:**
- Produces:
  - `OsrmWorker(QThread)` — `__init__(waypoints, transport)`; signals `route_ready(object)` (a `Route`), `route_failed(str)`; calls `routing.build_route` in `run()`.
  - `PipelineWorker(QThread)` — `__init__(plan)`; signals `log(str)`, `stage(str)`, `finished_rc(int)`; runs generate then transmit via `QProcess`, streaming stdout; `stop()` kills the active process; never auto-advances to transmit if generate fails.
  - `PlaybackWorker(QThread)` — `__init__(trajectory)`; signal `position(float,float,float)` (lat,lng,progress%); advances by wall-clock vs `trajectory[i].t_s`; `stop()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_workers_import.py
import pytest
pytest.importorskip("PyQt6.QtCore")

def test_workers_importable():
    from ghostsignal.workers.osrm_worker import OsrmWorker
    from ghostsignal.workers.pipeline_worker import PipelineWorker
    from ghostsignal.workers.playback_worker import PlaybackWorker
    assert OsrmWorker and PipelineWorker and PlaybackWorker
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_workers_import.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

```python
# ghostsignal/workers/osrm_worker.py
from PyQt6.QtCore import QThread, pyqtSignal
from ..core import routing

class OsrmWorker(QThread):
    route_ready = pyqtSignal(object)
    route_failed = pyqtSignal(str)
    def __init__(self, waypoints, transport):
        super().__init__(); self.waypoints = waypoints; self.transport = transport
    def run(self):
        try:
            self.route_ready.emit(routing.build_route(self.waypoints, self.transport))
        except Exception as e:
            self.route_failed.emit(str(e))
```

```python
# ghostsignal/workers/pipeline_worker.py
from PyQt6.QtCore import QThread, pyqtSignal, QProcess, QEventLoop

class PipelineWorker(QThread):
    log = pyqtSignal(str)
    stage = pyqtSignal(str)
    finished_rc = pyqtSignal(int)
    def __init__(self, plan):
        super().__init__(); self.plan = plan; self._proc = None; self._abort = False

    def _run_step(self, argv) -> int:
        self._proc = QProcess()
        self._proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        loop = QEventLoop()
        self._proc.readyReadStandardOutput.connect(
            lambda: self.log.emit(bytes(self._proc.readAllStandardOutput()).decode(errors="replace").rstrip()))
        self._proc.finished.connect(lambda *_: loop.quit())
        self._proc.start(argv[0], argv[1:])
        loop.exec()
        return self._proc.exitCode()

    def run(self):
        # write motion file first
        with open(self.plan.motion_path, "w", encoding="utf-8") as f:
            f.write(self.plan.motion_text)
        self.stage.emit("generate")
        if self._abort: return
        rc = self._run_step(self.plan.gen_argv)
        if rc != 0 or self._abort:
            self.finished_rc.emit(rc); return
        self.stage.emit("transmit")
        rc = self._run_step(self.plan.tx_argv)
        self.finished_rc.emit(rc)

    def stop(self):
        self._abort = True
        if self._proc:
            self._proc.kill()
```

```python
# ghostsignal/workers/playback_worker.py
import time
from PyQt6.QtCore import QThread, pyqtSignal

class PlaybackWorker(QThread):
    position = pyqtSignal(float, float, float)
    def __init__(self, trajectory):
        super().__init__(); self.traj = trajectory; self._stop = False
    def stop(self): self._stop = True
    def run(self):
        if not self.traj: return
        total = self.traj[-1].t_s or 1.0
        start = time.time()
        while not self._stop:
            el = time.time() - start
            i = min(range(len(self.traj)), key=lambda k: abs(self.traj[k].t_s - el))
            p = self.traj[i]
            self.position.emit(p.lat, p.lng, min(el / total * 100, 100))
            if el >= total: break
            time.sleep(0.2)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_workers_import.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/workers tests/test_workers_import.py
git commit -m "feat: add OSRM/pipeline/playback QThread workers"
```

---

## Task 18: Dialogs + panels (`ui/dialogs.py`, `ui/left_panel.py`, `ui/right_panel.py`, `ui/widgets.py`)

**Files:**
- Create: `ghostsignal/ui/widgets.py`, `ghostsignal/ui/dialogs.py`, `ghostsignal/ui/left_panel.py`, `ghostsignal/ui/right_panel.py`
- Test: `tests/test_panels_import.py`

**Interfaces:**
- Produces:
  - `widgets.labeled_group(title, inner: QWidget) -> QGroupBox`.
  - `dialogs.AuthorizationDialog(QDialog)` — modal; `exec()` returns accepted only if the "I am authorized / shielded environment" checkbox is ticked; `@staticmethod confirm(parent) -> bool`.
  - `dialogs.SettingsDialog(QDialog)` — fields for each tool path + Earthdata credentials; `values() -> dict`.
  - `LeftPanel(QWidget)` — session name, transport combo, speed controls (cruise + accel/decel when trapezoidal), start-time edit, waypoint list + CLEAR, Save/Load buttons, NMEA-load button. Exposes the widgets as attributes and a `signals` object with `cleared`, `save_requested`, `load_requested`, `nmea_requested`, `transport_changed(str)`.
  - `RightPanel(QWidget)` — constellation combo (greys unavailable), device combo, frequency spin + presets, gain slider, sample-rate combo, planner-only checkbox, TRANSMIT/STOP button, progress bar, CLI/LOG tabs with Copy/Save. Exposes attributes + `signals` with `transmit_toggled`, `constellation_changed`, `freq_changed`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_panels_import.py
import pytest
pytest.importorskip("PyQt6.QtWidgets")
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

def test_panels_construct():
    from ghostsignal.ui.left_panel import LeftPanel
    from ghostsignal.ui.right_panel import RightPanel
    from ghostsignal.ui.dialogs import AuthorizationDialog, SettingsDialog
    lp, rp = LeftPanel(), RightPanel()
    assert lp.transport_combo.count() == 5
    assert rp.constellation_combo.count() == 4
    assert hasattr(AuthorizationDialog, "confirm")
    assert hasattr(SettingsDialog, "values")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_panels_import.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

Implement the four files. `widgets.labeled_group` wraps a widget in a `QGroupBox` with a vertical layout. `AuthorizationDialog` shows the legal notice text (from the spec §1) + a required checkbox gating the OK button; `confirm(parent)` constructs it, calls `exec()`, returns `True` only on accept. `SettingsDialog` builds a `QFormLayout` of `QLineEdit`s keyed by tool name + two Earthdata fields; `values()` returns `{key: text}`. `LeftPanel`/`RightPanel` reproduce v1's left/right panel widgets (see `ghostsignal.py` `_make_left_panel` lines ~576–658 and `_make_right_panel` lines ~674–788) but as standalone `QWidget` subclasses exposing the widgets as attributes and emitting the listed signals (define a small `QObject` `signals` holder per panel). The constellation combo lists GPS/Galileo/GLONASS/BeiDou; a `set_available(constellation, bool)` method disables the row for unavailable backends. Keep styling via object names so the global `style.qss` applies. Build the accel/decel spinboxes and show/hide them when the speed-profile kind toggles.

Because this task is pure widget assembly, the gate is: the panels construct without error, expose the asserted attributes/counts, and the authorization + settings dialogs expose their documented API. Detailed widget code follows v1 one-to-one; no new logic beyond signal wiring.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_panels_import.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/ui/widgets.py ghostsignal/ui/dialogs.py ghostsignal/ui/left_panel.py ghostsignal/ui/right_panel.py tests/test_panels_import.py
git commit -m "feat: add UI panels, authorization gate, and settings dialog"
```

---

## Task 19: Main window + app bootstrap (`ui/main_window.py`, `app.py`)

**Files:**
- Create: `ghostsignal/ui/main_window.py`, `ghostsignal/app.py`
- Modify: `ghostsignal/__main__.py` (already calls `app.main`)
- Test: `tests/test_mainwindow_import.py`

**Interfaces:**
- Consumes: `LeftPanel`, `RightPanel`, `MapPanel`, workers, `ToolConfig`, `build_registry`, transmitters, `routing`, `motion`, `pipeline`, `session`, `rinex`, `cli`, `dialogs`.
- Produces:
  - `MainWindow(QMainWindow)` — assembles the three panels in a splitter + top bar + status bar; wires: map click→add waypoint→refresh markers→OSRM worker→draw route→update CLI; transport change→respeed+reroute; TRANSMIT→(if not planner-only) `AuthorizationDialog.confirm` gate→build trajectory→`plan_pipeline`→`PipelineWorker`+`PlaybackWorker`; STOP→kill workers; Save/Load/NMEA/ephemeris actions. Exposes `build_current_plan()` returning a `PipelinePlan` for the current state (used by a dry-run smoke step).
  - `app.main() -> None` — `QApplication`, load `style.qss`, apply palette, show `MainWindow`, `exec()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_mainwindow_import.py
import pytest
pytest.importorskip("PyQt6.QtWebEngineWidgets")
from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

def test_mainwindow_builds_and_plans():
    from ghostsignal.ui.main_window import MainWindow
    from ghostsignal.core.models import Waypoint
    w = MainWindow()
    w.waypoints = [Waypoint(42.0, 23.0), Waypoint(42.05, 23.05)]
    w._refresh_waypoints()
    plan = w.build_current_plan(nav_file="brdc.nav")
    assert plan.gen_argv[0].endswith("gps-sdr-sim") or plan.gen_argv[0] == "gps-sdr-sim"
    assert plan.tx_argv[0].endswith("hackrf_transfer") or plan.tx_argv[0] == "hackrf_transfer"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_mainwindow_import.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Write minimal implementation**

Implement `MainWindow` assembling `LeftPanel`/`MapPanel`/`RightPanel` in a `QSplitter`, reproducing v1's top bar/status bar/logging, and wiring the signals as described in Interfaces. Factor a `build_current_plan(nav_file)` that: builds a `Route` from current waypoints+transport (synchronously via `routing.build_route` for the plan path), a trajectory via `motion.build_trajectory` using the current `SpeedProfile`, resolves the backend from `build_registry(self.cfg)[constellation]` and the transmitter from the device combo, and returns `pipeline.plan_pipeline(...)`. The TRANSMIT handler: if `planner_only`, generate+show the CLI/script only; else call `AuthorizationDialog.confirm(self)` and abort if declined, then start `PipelineWorker(plan)` + `PlaybackWorker(trajectory)`, wiring `log`→system log, `stage`→status, `position`→`MapPanel.update_position`+progress, `finished_rc`→reset. STOP kills both workers. `app.main()` loads `style.qss` from assets, applies the palette (copy v1's palette block), shows the window.

Gate: window constructs headless (offscreen), `build_current_plan` returns a wired `PipelinePlan`.

- [ ] **Step 4: Run test to verify it passes**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_mainwindow_import.py -v` (offscreen so no display is needed)
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add ghostsignal/ui/main_window.py ghostsignal/app.py tests/test_mainwindow_import.py
git commit -m "feat: assemble main window + app bootstrap, wire panels/workers/pipeline"
```

---

## Task 20: Windows build & setup scripts (`scripts/`)

**Files:**
- Create: `scripts/build-gps-sdr-sim.ps1`, `scripts/build-galileo-sdr-sim.ps1`
- (`scripts/setup-venv.ps1` already created in Task 1.)

**Interfaces:**
- Produces: PowerShell scripts that locate/clone the C sim sources, compile with mingw `gcc` (bumping `USER_MOTION_SIZE`), and print the resulting `.exe` path for the user to set via env/config.

- [ ] **Step 1: Write `scripts/build-gps-sdr-sim.ps1`**

```powershell
# scripts/build-gps-sdr-sim.ps1
param(
  [string]$Src = "$HOME\gps-sdr-sim",
  [int]$MotionSize = 36000      # 3600 s @ 10 Hz
)
if (-not (Test-Path $Src)) {
  git clone https://github.com/osqzss/gps-sdr-sim.git $Src
}
$gcc = (Get-Command gcc -ErrorAction SilentlyContinue)
if (-not $gcc) { throw "gcc not found on PATH (install mingw-w64 / use Git Bash toolchain)" }
$out = Join-Path $Src "gps-sdr-sim.exe"
& gcc "$Src\gpssim.c" -lm -O3 "-DUSER_MOTION_SIZE=$MotionSize" -o $out
Write-Host "Built: $out"
Write-Host "Set it with:  `$env:GPS_SDR_SIM = '$out'"
```

- [ ] **Step 2: Write `scripts/build-galileo-sdr-sim.ps1`**

```powershell
# scripts/build-galileo-sdr-sim.ps1
param([string]$Src = "$HOME\galileo-sdr-sim")
if (-not (Test-Path $Src)) {
  git clone https://github.com/harshadms/galileo-sdr-sim.git $Src
}
Write-Host "galileo-sdr-sim uses CMake. From a MinGW/MSYS2 shell:"
Write-Host "  cd '$Src'; mkdir build; cd build; cmake .. -G 'MinGW Makefiles'; mingw32-make"
Write-Host "Then set:  `$env:GALILEO_SDR_SIM = '$Src\build\galileo-sdr-sim.exe'"
```

- [ ] **Step 3: Attempt the gps-sdr-sim build (best-effort on this machine)**

Run (Git Bash): `gcc ~/gps-sdr-sim/gpssim.c -lm -O3 -DUSER_MOTION_SIZE=36000 -o ~/gps-sdr-sim/gps-sdr-sim.exe && echo BUILT`
Expected: `BUILT` and a working `gps-sdr-sim.exe`. If `gcc` is missing or build fails, record the error in the commit message and leave the script for the user to run — this does not block the task.

- [ ] **Step 4: Commit**

```bash
git add scripts/build-gps-sdr-sim.ps1 scripts/build-galileo-sdr-sim.ps1
git commit -m "feat: add Windows build scripts for gps-sdr-sim and galileo-sdr-sim"
```

---

## Task 21: Dockerfile (headless generation)

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`

**Interfaces:**
- Produces: a headless image that installs the package (no GUI extras needed for `ghostsignal-cli`) and builds `gps-sdr-sim` for IQ generation. Documented caveat: live USB TX from the container is out of scope.

- [ ] **Step 1: Write `Dockerfile`**

```dockerfile
# Dockerfile — headless GNSS IQ generation (no live TX)
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
      git build-essential && rm -rf /var/lib/apt/lists/*
RUN git clone https://github.com/osqzss/gps-sdr-sim.git /opt/gps-sdr-sim && \
    gcc /opt/gps-sdr-sim/gpssim.c -lm -O3 -DUSER_MOTION_SIZE=36000 \
        -o /usr/local/bin/gps-sdr-sim
ENV GPS_SDR_SIM=/usr/local/bin/gps-sdr-sim
WORKDIR /app
COPY pyproject.toml /app/
COPY ghostsignal /app/ghostsignal
RUN pip install --no-cache-dir -e . --no-deps   # headless CLI has no hard Qt need
ENTRYPOINT ["ghostsignal-cli"]
CMD ["--help"]
```

- [ ] **Step 2: Write `docker-compose.yml` and `.dockerignore`**

```yaml
# docker-compose.yml
services:
  ghostsignal:
    build: .
    volumes:
      - ./work:/work
    command: ["run", "/work/session.json", "--generate-only", "--nav", "/work/brdc.nav", "--work-dir", "/work"]
```

```
# .dockerignore
.venv/
__pycache__/
*.bin
*.nav
docs/
tests/
```

Note: `ghostsignal-cli` imports only `core`/`backends`/`sdr`/`pipeline` (no PyQt6), so `--no-deps` install keeps the image GUI-free. Add a README caveat that Docker is for generation, host for TX.

- [ ] **Step 3: Commit**

```bash
git add Dockerfile docker-compose.yml .dockerignore
git commit -m "feat: add headless Docker image for IQ generation"
```

---

## Task 22: README rewrite + final parity check + remove v1

**Files:**
- Modify: `README.md`
- Delete: `ghostsignal.py` (v1 monolith — superseded; remains in git history)
- Modify: `requirements.txt` (point to `pip install -e .`)

**Interfaces:**
- Produces: updated docs reflecting v2 (modular layout, real TX, continuous routes, multi-constellation honesty, Windows-first setup, headless/Docker, the authorization requirement). No code behavior.

- [ ] **Step 1: Rewrite `README.md`**

Update the README to describe v2: new run commands (`python -m ghostsignal`, `ghostsignal-cli run session.json`), the Python 3.12 venv requirement, the two build scripts, the multi-constellation reality (GPS + Galileo real; GLONASS/BeiDou via a configurable external multi-GNSS tool), the continuous-motion feature, the RINEX downloader + CDDIS/Earthdata note, the headless/Docker caveat (generation only), and keep/強化 the legal-authorization notice. Remove the misleading L2/L5 "constellation" framing. Keep MIT license and credits (add harshadms/galileo-sdr-sim and the multi-GNSS tool).

- [ ] **Step 2: Update `requirements.txt`**

```
# Runtime deps are declared in pyproject.toml. For a dev install:
#   python -m pip install -e ".[dev]"
PyQt6>=6.6.0
PyQt6-WebEngine>=6.6.0
```

- [ ] **Step 3: Remove v1 monolith**

Run (Git Bash): `git rm ghostsignal.py`
(v1 stays recoverable from history / the `master` branch.)

- [ ] **Step 4: Full test sweep (user-run per machine policy)**

Request the user run: `python -m pytest -q` on the activated 3.12 venv.
Expected: all tests pass. Also run the dry-run smoke: `ghostsignal-cli run <a saved session>.json --dry-run --nav brdc.nav` and confirm two argv lines print. For GUI: `python -m ghostsignal` launches, map loads, a waypoint can be placed, a route draws, the CLI tab fills, the authorization gate appears before a real (non-planner) transmit.

- [ ] **Step 5: Commit**

```bash
git add README.md requirements.txt
git commit -m "docs: rewrite README for v2; remove v1 monolith (kept in history)"
```

---

## Self-Review

**1. Spec coverage** — every spec section maps to a task:
- §3 architecture / pure-core rule → Task 1 (`test_architecture`), enforced throughout.
- §4 models → Task 3. §5.1 motion/continuous → Task 5. §5.2 speed profile → Task 5. §5.3 NMEA → Task 6. §5.4 backends/multi-constellation → Task 7. §5.4 SDR → Task 8. §5.5 pipeline+safety → Tasks 13 (pipeline), 17 (worker hard-stop), 18 (authorization gate), 19 (wiring + planner-only). §5.6 honest playback → Task 17 (`PlaybackWorker` wall-clock) + 19. §5.7 RINEX → Task 11 + config §12. §5.8 headless/Docker → Tasks 14, 21.
- §6 theming/UI → Tasks 15–19. §7 Windows setup → Tasks 1, 20. §8 testing → every task + `test_architecture`. §9 risks → surfaced in Tasks 20 (build best-effort), 21 (Docker caveat), 22 (README). §11 milestones → task ordering.

**2. Placeholder scan** — Tasks 18 and 19 describe widget/window assembly in prose rather than full literal code, because they are one-to-one reproductions of v1's `_make_left_panel`/`_make_right_panel`/main-window blobs (cited by line range) plus signal wiring; their gates are concrete (asserted attributes, counts, `build_current_plan` output). All other tasks carry real, runnable code. No "TODO/implement later" remain.

**3. Type consistency** — backend `build_argv(**kwargs)` signature is identical across `base`, `gps_sdr_sim`, `galileo_sdr_sim`, `glonass`, `beidou`, and is consumed with the same keywords in `cli.build_script` (Task 9) and `pipeline.plan_pipeline` (Task 13). `SdrTransmitter.build_argv(iq_file, freq_hz, sample_rate, gain_db)` is consistent in Tasks 8, 9, 13. `Route`/`Waypoint`/`SpeedProfile`/`SdrConfig`/`Session` field names match between Task 3 and their consumers (routing, motion, session, pipeline, headless). Map JS API names (`addMarker`/`clearMarkers`/`drawRoute`/`drawStraightLine`/`updatePosition`/`clearPosition`) match between Task 15 asset and Task 16 `MapPanel`.
