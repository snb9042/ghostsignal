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
