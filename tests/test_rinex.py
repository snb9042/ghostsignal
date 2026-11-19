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

RINEX_NAV = b"     2              NAVIGATION DATA                         RINEX VERSION / TYPE\n"

def test_looks_like_rinex():
    assert rinex.looks_like_rinex(RINEX_NAV)
    assert not rinex.looks_like_rinex(b"<!DOCTYPE html><title>Earthdata Login</title>")

def test_ensure_downloads_and_decompresses(tmp_path):
    import gzip
    payload = gzip.compress(RINEX_NAV)
    calls = []
    def fetch(url):
        calls.append(url)
        if url.endswith(".gz"):
            return payload
        raise OSError("404")
    path = rinex.ensure_ephemeris(datetime.date(2026, 1, 1), str(tmp_path), fetch=fetch)
    assert open(path, "rb").read() == RINEX_NAV
    assert calls                                   # attempted at least one URL

def test_ensure_skips_non_rinex(tmp_path):
    # A mirror returns a 200 HTML login page (the CDDIS-auth bug); a later
    # mirror returns real RINEX. The HTML must be skipped, not cached.
    html = b"<!DOCTYPE html><html><title>Earthdata Login</title></html>"
    calls = []
    def fetch(url):
        calls.append(url)
        if url.endswith(".gz"):
            raise OSError("404")                   # force the plain-name path
        plains = [u for u in calls if not u.endswith(".gz")]
        return html if len(plains) == 1 else RINEX_NAV   # 1st plain HTML, 2nd RINEX
    path = rinex.ensure_ephemeris(datetime.date(2026, 1, 1), str(tmp_path), fetch=fetch)
    assert open(path, "rb").read() == RINEX_NAV   # cached the real RINEX
    assert sum(1 for u in calls if not u.endswith(".gz")) >= 2  # passed the HTML page

def test_build_request_attaches_token_to_cddis():
    r = rinex.build_request("https://cddis.nasa.gov/archive/x/brdc0010.26n.gz", token="Tok123")
    assert r.get_header("Authorization") == "Bearer Tok123"

def test_build_request_no_token_no_header():
    r = rinex.build_request("https://cddis.nasa.gov/archive/x/brdc0010.26n.gz", token=None)
    assert r.get_header("Authorization") is None

def test_build_request_never_leaks_token_to_other_hosts():
    # The Earthdata token must NOT be sent to non-Earthdata mirrors (e.g. IGN).
    r = rinex.build_request("https://igs.ign.fr/pub/igs/data/2026/001/brdc0010.26n.gz", token="Tok123")
    assert r.get_header("Authorization") is None

def test_earthdata_token_from_env(monkeypatch):
    monkeypatch.setenv("EARTHDATA_TOKEN", "  envtok  ")
    assert rinex.earthdata_token() == "envtok"

def test_ensure_rejects_all_non_rinex(tmp_path):
    # Every mirror returns a 200 HTML page -> clean error, nothing cached.
    def fetch(url):
        return b"<!DOCTYPE html><title>login</title>"
    with pytest.raises(rinex.EphemerisError):
        rinex.ensure_ephemeris(datetime.date(2026, 1, 1), str(tmp_path), fetch=fetch)
    assert list(tmp_path.iterdir()) == []          # no poisoned cache file

def test_ensure_raises_when_all_fail(tmp_path):
    def fetch(url): raise OSError("down")
    with pytest.raises(rinex.EphemerisError):
        rinex.ensure_ephemeris(datetime.date(2026, 1, 1), str(tmp_path), fetch=fetch)
