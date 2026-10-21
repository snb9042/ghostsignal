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

def test_script_quotes_shell_metacharacters():
    import shlex
    sdr = SdrConfig("HackRF One", Constellation.GPS, 1_575_420_000, 2_600_000, 30)
    s = build_script(generator=GpsSdrSim("gps-sdr-sim"),
                     transmitter=HackRfTransmitter("hackrf_transfer"),
                     nav_file="brdc.nav;reboot", motion_file="m.csv", motion_fmt="llh",
                     start_time="t", duration_s=10, sdr=sdr, planner_note=False)
    assert shlex.quote("brdc.nav;reboot") in s   # dangerous arg is shell-quoted, not injected
