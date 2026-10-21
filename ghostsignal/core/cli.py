from __future__ import annotations
import shlex

OUT_BIN = "gps_sim.bin"

def _fmt(argv) -> str:
    return " ".join(shlex.quote(a) for a in argv)

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
