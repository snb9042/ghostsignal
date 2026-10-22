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
