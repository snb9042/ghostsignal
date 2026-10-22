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
