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
