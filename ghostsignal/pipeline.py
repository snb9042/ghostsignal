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
