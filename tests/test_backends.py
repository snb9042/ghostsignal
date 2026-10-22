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
