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
