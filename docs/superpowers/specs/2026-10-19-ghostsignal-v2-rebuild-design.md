# GhostSignal v2 — Rebuild Design Spec

**Date:** 2026-10-19
**Status:** Approved for planning
**Author:** rebuild/v2 branch
**Supersedes:** GhostSignal v1.0 (`ghostsignal.py`, single-file monolith)

---

## 1. Purpose & Context

GhostSignal is a desktop GUI for planning, generating, and transmitting
GNSS signals with SDR hardware (HackRF One, LimeSDR) for **authorized
research, development, and testing** — Faraday-cage labs, sanctioned
drone-test ranges, and academic work with proper permission.

v1 is a working but monolithic ~1,180-line PyQt6 file with two notable
gaps that v2 fixes:

1. It only ever transmits a **static** position (`gps-sdr-sim -l lat,lng`).
   The on-map "movement" is a cosmetic timer, not a moving GPS fix.
2. The "TRANSMIT" button never actually drives the SDR; it only animates
   a dot. The real work is a copy-paste shell script the user runs by hand.
   Its multi-constellation claim (GLONASS/Galileo/BeiDou) is aspirational —
   the only backend is GPS-only `gps-sdr-sim`, and the L2/L5 presets are
   misleading (gps-sdr-sim emits L1 C/A baseband regardless).

**v2 goal:** a clean, modular, tested rebuild that (a) actually drives the
SDR end-to-end, (b) produces genuinely **continuous moving-fix** playback,
and (c) makes multi-constellation real via a pluggable backend seam —
GPS and Galileo as verified backends, GLONASS/BeiDou wired to a
configurable external multi-GNSS tool.

### Scope (confirmed with user)

Full v2 roadmap in a single spec, **Windows-primary** (the dev machine):
modular rewrite + real SDR execution + continuous route playback +
speed accel/decel + NMEA replay + RINEX downloader + multi-constellation
(GPS + Galileo real; GLONASS + BeiDou via external tool) + headless/Docker.

---

## 2. Environment Baseline (verified on dev machine)

| Component | State | Implication |
|---|---|---|
| `hackrf_transfer`, `SoapySDRUtil` | Present (PothosSDR, `C:\Program Files\PothosSDR\bin`) | Real HackRF TX viable on this box; auto-detect this path. |
| `gps-sdr-sim` | Source at `~/gps-sdr-sim`, **not compiled**, not on PATH | Provide Windows build script (mingw `gcc`). |
| `galileo-sdr-sim` | Not present | Clone + build script; real Galileo E1B/C backend. |
| GLONASS/BeiDou sim | None | Configurable external tool (`gnss-signal-simulator-rs`); experimental. |
| Python | 3.14 default, **PyQt6 not installed** on 3.14 or 3.12 | Target a **Python 3.12 venv** (PyQt6 has no 3.14 wheels yet). |
| mingw64 `gcc` | On PATH (Git Bash) | Used to compile the C simulators. |
| Sibling project `~/gps-hackrf-sim-newlast` | Modular PyQt app w/ extracted `map.html`, `dark.qss`, Linux packaging | Borrow asset-extraction + packaging patterns. |

**External tool facts relied upon:**
- `gps-sdr-sim` flags (confirmed in local `gpssim.c`): `-e` nav, `-u` ECEF
  motion, `-x` lat/lng/height motion, `-g` NMEA GGA, `-l` static, `-t`/`-T`
  time, `-d` duration, `-s` sample rate, `-b` I/Q bits, `-o` output, `-i` iono.
- `USER_MOTION_SIZE = 3000` (300 s @ 10 Hz) default cap in `gpssim.h`.
- User-motion `-x` format (from `circle_llh.csv`): `time_s, lat, lng, height`
  at 10 Hz.
- HackRF requires **8-bit** I/Q → generators must emit `-b 8` for the HackRF path.
- `galileo-sdr-sim` (harshadms): Galileo E1B/C, HackRF/LimeSDR/USRP, dynamic
  trajectory, centered 1575.42 MHz.

---

## 3. Architecture

**Principle:** a **pure, Qt-free `core/`** that holds all logic and is fully
unit-testable without a display, plus a thin Qt UI layer that imports core
(never the reverse). This boundary is also what makes headless/Docker possible.

```
ghostsignal/
├─ pyproject.toml              # metadata, deps, console entry points
├─ requirements.txt           # pinned runtime deps
├─ README.md                  # updated, honest, Windows-first setup
├─ LICENSE                    # unchanged (MIT)
├─ Dockerfile / docker-compose.yml
├─ ghostsignal/
│  ├─ __init__.py             # __version__ = "2.0.0"
│  ├─ __main__.py             # `python -m ghostsignal` → GUI
│  ├─ app.py                  # QApplication bootstrap, theme/palette load
│  ├─ config.py               # Settings: tool paths (env + QSettings), prefs
│  ├─ constants.py            # freqs, transport speeds, OSRM profiles, constellations
│  ├─ core/                   # ── NO PyQt import anywhere in this package ──
│  │  ├─ geo.py               # haversine, lla<->ecef, interpolation, bearing
│  │  ├─ models.py            # dataclasses (see §4)
│  │  ├─ routing.py           # OSRMClient (urllib) + straight-line → Route
│  │  ├─ motion.py            # Route + SpeedProfile → trajectory @10Hz; writers
│  │  ├─ nmea.py              # parse .nmea GGA/RMC track → Route/trajectory
│  │  ├─ cli.py               # pure argv + bash-script builders per backend/device
│  │  ├─ session.py           # Session ⇄ JSON (schema v2) + migrate v1
│  │  └─ rinex.py             # ephemeris sources, download+cache, decompress
│  ├─ backends/               # signal generators (constellation sims)
│  │  ├─ base.py              # SignalGenerator ABC
│  │  ├─ registry.py          # discover/instantiate from config
│  │  ├─ gps_sdr_sim.py       # GPS  (gps-sdr-sim)            [REAL]
│  │  ├─ galileo_sdr_sim.py   # Galileo E1B/C (galileo-sdr-sim) [REAL]
│  │  ├─ glonass.py           # GLONASS (external multi-GNSS)  [experimental]
│  │  └─ beidou.py            # BeiDou  (external multi-GNSS)  [experimental]
│  ├─ sdr/                    # transmitters
│  │  ├─ base.py              # SdrTransmitter ABC
│  │  ├─ hackrf.py            # hackrf_transfer                [REAL]
│  │  └─ limesdr.py           # SoapySDR
│  ├─ pipeline.py             # generate→transmit orchestrator (callback events)
│  ├─ ui/
│  │  ├─ main_window.py
│  │  ├─ left_panel.py right_panel.py map_panel.py
│  │  ├─ bridge.py widgets.py dialogs.py
│  │  └─ assets/  map.html  style.qss  icon.svg
│  ├─ workers/
│  │  ├─ osrm_worker.py       # QThread wrapping core.routing
│  │  ├─ pipeline_worker.py   # QProcess chain; live log; hard stop
│  │  └─ playback_worker.py   # map dot from real elapsed TX vs trajectory time
│  └─ headless/
│     └─ cli.py               # `ghostsignal-cli run session.json` (no Qt)
├─ tests/                     # pytest; pure core + dry-run pipeline (no display)
└─ scripts/
   ├─ build-gps-sdr-sim.ps1
   ├─ build-galileo-sdr-sim.ps1
   └─ setup-venv.ps1
```

**Import rule (enforced by a test):** nothing under `ghostsignal/core`,
`ghostsignal/backends`, or `ghostsignal/sdr` may import `PyQt6`.

---

## 4. Core Data Models (`core/models.py`)

Plain `@dataclass` types, JSON-serializable, no Qt:

- `Waypoint(lat, lng, alt=100.0)`
- `Route(waypoints: list[Waypoint], geometry: dict|None, distance_km, source)`
  — `source` ∈ {`osrm`, `straight`, `nmea`}.
- `TrajectoryPoint(t_s, lat, lng, alt)` — one 10 Hz sample.
- `SpeedProfile(kind, cruise_kmh, accel_ms2=None, decel_ms2=None)` —
  `kind` ∈ {`constant`, `trapezoidal`}.
- `Constellation(Enum)` — `GPS`, `GALILEO`, `GLONASS`, `BEIDOU`.
- `SdrConfig(device, constellation, freq_hz, sample_rate_hz, tx_gain_db,
  iq_bits, enable_iono)`.
- `Session(name, transport, speed_profile, start_time_utc, waypoints,
  sdr: SdrConfig, planner_only: bool, schema="2")`.

---

## 5. Feature Designs

### 5.1 Continuous route playback (the core win)
`motion.py` converts a `Route` + `SpeedProfile` into a list of
`TrajectoryPoint` at **10 Hz**:
1. Resample the route polyline by arc length using the speed profile
   (constant → uniform spacing; trapezoidal → accel ramp, cruise,
   decel ramp bounded by `accel/decel` m/s²).
2. Interpolate lat/lng/alt along segments (great-circle via `geo.py`).
3. Emit writers: `to_llh_csv()` (`-x`), `to_ecef_csv()` (`-u`),
   `to_nmea_gga()` (`-g`).

**Duration cap handling** (`USER_MOTION_SIZE = 300 s`): if the trajectory
exceeds the sim's compiled cap, either (a) use a sim recompiled with a
larger buffer (build script passes `-DUSER_MOTION_SIZE=…`, **preferred**),
or (b) split the trajectory into ≤300 s chunks, generate a `.bin` per
chunk, and concatenate (`copy /b` on Windows) before transmit. The chosen
strategy is a setting; default = recompiled-large-buffer, fall back to
chunking if the sim reports the cap.

### 5.2 Speed profile (accel/decel)
Trapezoidal profile in `motion.py`: ramp from 0 to cruise at `accel`, hold,
ramp down to 0 at `decel`. Pure math, fully unit-tested against known
distance/time integrals. UI exposes cruise speed + optional accel/decel.

### 5.3 NMEA replay
`nmea.py` parses `$GPGGA`/`$GNGGA` (position, alt) and optionally
`$..RMC` (speed/time) from a `.nmea` file into a `Route`/trajectory,
bypassing routing entirely. Feeds the same generate→transmit pipeline.

### 5.4 Backend seam & multi-constellation
`SignalGenerator` ABC:
```
name: str
constellation: Constellation
default_freq_hz: int
def available(self) -> bool            # binary resolvable + runnable
def build_argv(self, *, nav_file, motion_file, motion_fmt,
               start_time, duration_s, sample_rate, iq_bits,
               iono, out_file) -> list[str]
supported_motion_formats: set[str]      # {"llh","ecef","nmea"}
```
- `gps_sdr_sim` — **REAL**. `-e nav -x motion.csv -b 8 -o out.bin …`.
- `galileo_sdr_sim` — **REAL**. Galileo E1B/C; argv per harshadms CLI
  (verified at implementation time against its `--help`).
- `glonass`, `beidou` — route to a **configurable external multi-GNSS tool**
  (default target: `gnss-signal-simulator-rs`). `available()` is false unless
  the user has configured a working binary; the UI greys the option and shows
  an "install/configure <tool>" hint. The interface, command-building, and
  session plumbing are fully implemented regardless.
- `registry.py` instantiates backends from `config` (per-tool path, env
  override like v1's `GPS_SDR_SIM`/`HACKRF_TRANSFER`).

`SdrTransmitter` ABC → `hackrf` (`hackrf_transfer -t file -f FREQ -s RATE
-a 1 -x GAIN -R`) and `limesdr` (SoapySDR TX). `available()` auto-detects
PothosSDR path on Windows.

### 5.5 Execution pipeline & safety
`pipeline.py` (pure, callback-based) sequences: **validate → write motion
file → run generator → run transmitter**, emitting typed progress events
(`stage`, `log_line`, `progress`, `done`, `error`). `pipeline_worker.py`
runs it over **QProcess** with live stdout/stderr streamed to the log and a
**hard Stop that terminates both** the generator and transmitter processes.

**Safety gates:**
- **Authorization modal** before the first *real* transmit each session:
  user must affirm an authorized/shielded environment. Logged with timestamp.
- **Planner-only toggle** (default honors v1 behavior option): generate the
  script + animate, never key the transmitter.
- Transmit disabled until a backend+transmitter pair both report `available()`.

### 5.6 Map playback (honest)
`playback_worker.py` advances the on-map position marker by looking up the
`TrajectoryPoint` for the **real elapsed transmit time**, so the dot matches
what the SDR is actually emitting (not a decoupled cosmetic timer).

### 5.7 RINEX / ephemeris downloader
`rinex.py`:
- Resolve the daily broadcast ephemeris (`brdc<DDD>0.<YY>n`) for the session
  date.
- **Configurable sources** with fallback order: local file → BKG/IGS mirror
  (no-auth) → CDDIS (needs Earthdata login, entered in Settings, stored via
  QSettings/keyring).
- Download to an AppData cache, auto-decompress `.gz`/`.Z` (Hatanaka `.crx`
  out of scope for v2 — document).
- UI: a "Download ephemeris for <date>" button + source/credentials settings.

### 5.8 Headless / Docker
`headless/cli.py` exposes `ghostsignal-cli run <session.json>
[--dry-run] [--generate-only]` using the same `core` + `pipeline`, no Qt
imported. `Dockerfile` builds the C sims for **IQ generation** headlessly.
**Caveat (documented):** reliable live USB TX from a Windows container is not
supported; Docker targets generation, with live TX on the host.

---

## 6. Theming & UI

Preserve v1's dark "terminal" aesthetic but move the stylesheet to
`ui/assets/style.qss` and the Leaflet document to `ui/assets/map.html`
(loaded from file, not an inline Python string). Panels become their own
modules (`left_panel`, `right_panel`, `map_panel`) wired by `main_window`.
Right panel gains: constellation selector (backends), planner-only toggle,
ephemeris download button, speed-profile controls. Status bar and system log
retained. Attribution updated; keep the legal notice prominent.

---

## 7. Windows-First Setup

- `scripts/setup-venv.ps1` — create a **Python 3.12** venv, `pip install -e .`.
- `scripts/build-gps-sdr-sim.ps1` — clone/locate source, `gcc gpssim.c -lm
  -O3 -DUSER_MOTION_SIZE=<large> -o gps-sdr-sim.exe`, record path in config.
- `scripts/build-galileo-sdr-sim.ps1` — clone + build galileo-sdr-sim.
- Auto-detect `C:\Program Files\PothosSDR\bin\hackrf_transfer.exe`.
- `pyproject.toml` console entry points: `ghostsignal` (GUI),
  `ghostsignal-cli` (headless).

---

## 8. Testing Strategy

- **Pure-core unit tests (pytest), no display needed:**
  `test_geo`, `test_motion` (trapezoidal integrals, 10 Hz count, cap/chunk
  logic), `test_routing` (mocked OSRM HTTP), `test_nmea`, `test_cli`
  (exact argv/script per backend+device, incl. `-b 8`), `test_session`
  (round-trip + v1 migration), `test_rinex` (filename/date resolution,
  source fallback, decompress with fixtures), `test_backends`
  (`available()` logic with fake binaries, argv shape).
- **Pipeline dry-run test:** full `generate→transmit` argv assembled without
  invoking hardware (`--dry-run`), asserted end-to-end.
- **Architecture test:** assert no `PyQt6` import under `core/backends/sdr`.
- Per user's environment constraint, **the agent does not run pytest**; the
  user runs the suite. Tests are written to be runnable on a plain 3.12 venv.

---

## 9. Risks & Honest Caveats

1. **RF correctness unverifiable here** — no hardware + shielded receiver;
   the agent verifies argv/scripts, dry-runs, orchestration, parsing, and all
   non-RF logic only.
2. **GLONASS/BeiDou** depend on an external multi-GNSS tool of uncertain
   maturity; shipped as configurable + experimental with clear UX, not faked.
3. **C sims must compile** with mingw `gcc`; build scripts provided; the
   agent may attempt the build but success depends on the local toolchain.
4. **Docker live TX on Windows** is unreliable (USB passthrough); Docker is
   for generation only — documented, not solved.
5. **CDDIS** requires an Earthdata login for that source; mirrors used
   otherwise; Hatanaka-compressed RINEX is out of scope for v2.
6. **PyQt6 / Python 3.14** — no wheels yet; v2 targets a 3.12 venv.

---

## 10. Out of Scope (v2)

- Hatanaka `.crx` RINEX decompression.
- Real-time closed-loop receiver feedback.
- Non-Windows packaging beyond "it still runs" (Linux/.desktop deferred to a
  follow-up, borrowing from `~/gps-hackrf-sim-newlast`).
- RF-validity validation of GLONASS/BeiDou output.

---

## 11. Milestones (for the implementation plan)

1. **Scaffold & core models** — package layout, `pyproject`, models, constants,
   `geo`, the no-Qt import test.
2. **Routing + motion + NMEA** — OSRM client, trajectory generation, speed
   profiles, motion-file writers, NMEA parse; unit tests.
3. **Backends + SDR + CLI builders** — ABCs, registry, gps/galileo real,
   glonass/beidou external, hackrf/limesdr, `cli.py`; unit tests.
4. **Pipeline + session + RINEX** — orchestrator, dry-run, session JSON + v1
   migration, ephemeris downloader; unit tests.
5. **Qt UI** — panels, map assets, bridge, dialogs (auth, settings, RINEX),
   workers (osrm, pipeline, playback), wire to pipeline.
6. **Headless + Docker** — `ghostsignal-cli`, Dockerfile.
7. **Windows build/setup scripts + README** — venv, sim builds, docs.
8. **Verification pass** — dry-run end-to-end, attempt sim builds, (user runs
   pytest), manual GUI smoke where possible.
