from __future__ import annotations
import datetime, gzip, os, urllib.parse, urllib.request
from pathlib import Path

class EphemerisError(Exception):
    pass

# NASA CDDIS requires Earthdata Login. We authenticate with a bearer token
# (an Earthdata "user token" from https://urs.earthdata.nasa.gov) rather than a
# stored password: it is revocable and never written to disk by us. The token
# is read from $EARTHDATA_TOKEN, or from ~/.edl_token if that file exists.
_EARTHDATA_SUFFIXES = ("cddis.nasa.gov", "earthdata.nasa.gov")

def earthdata_token() -> str | None:
    tok = os.environ.get("EARTHDATA_TOKEN")
    if tok and tok.strip():
        return tok.strip()
    p = Path(os.path.expanduser("~")) / ".edl_token"
    try:
        if p.is_file():
            t = p.read_text(encoding="utf-8").strip()
            return t or None
    except OSError:
        pass
    return None

def _is_earthdata_host(host: str) -> bool:
    host = (host or "").lower()
    return any(host == s or host.endswith("." + s) for s in _EARTHDATA_SUFFIXES)

def build_request(url: str, token: str | None = None) -> urllib.request.Request:
    """Request for *url*, attaching the Earthdata bearer token ONLY to Earthdata
    hosts so the credential never leaks to other mirrors (e.g. IGN)."""
    if token is None:
        token = earthdata_token()
    headers = {}
    if token and _is_earthdata_host(urllib.parse.urlsplit(url).hostname or ""):
        headers["Authorization"] = "Bearer " + token
    return urllib.request.Request(url, headers=headers)

# Mirror bases, tried in order. IGN is no-auth and serves short-name RINEX 2
# GPS nav (brdcDDD0.YYn), which is what gps-sdr-sim parses. CDDIS is kept last:
# it requires NASA Earthdata auth -- with a bearer token (see earthdata_token)
# it returns real RINEX; unauthenticated it returns a 200 HTML login page, which
# looks_like_rinex() rejects so it is never cached. (The old BKG short-name path
# is dead: BKG moved to long-name RINEX 3 files, which gps-sdr-sim cannot parse.)
DEFAULT_SOURCES = [
    "https://igs.ign.fr/pub/igs/data/{yyyy}/{ddd}/",
    "https://cddis.nasa.gov/archive/gnss/data/daily/{yyyy}/brdc/",
]

def brdc_filename(date: datetime.date) -> str:
    ddd = date.timetuple().tm_yday
    return f"brdc{ddd:03d}0.{date.strftime('%y')}n"

def source_urls(date: datetime.date, sources=DEFAULT_SOURCES) -> list[str]:
    name = brdc_filename(date)
    ddd = f"{date.timetuple().tm_yday:03d}"
    urls = []
    for base in sources:
        b = base.format(yyyy=date.year, ddd=ddd)
        urls.append(b + name + ".gz")
        urls.append(b + name)
    return urls

def looks_like_rinex(data: bytes) -> bool:
    """True if the bytes look like a RINEX nav file.

    A valid RINEX file carries the literal 'RINEX VERSION' in its header line.
    This guards against caching non-RINEX bodies that still arrive with HTTP
    200 -- e.g. the CDDIS Earthdata login page returned to unauthenticated
    requests, or a mirror's HTML error page.
    """
    return "RINEX VERSION" in data[:1024].decode("latin-1", "ignore")

def decompress(name: str, data: bytes) -> bytes:
    """Decompress .gz files; plain files returned as-is.

    Only .gz (gzip) decompression is handled. Plain RINEX files are returned
    unchanged. .Z (compress) format is not supported.
    """
    if name.endswith(".gz"):
        return gzip.decompress(data)
    return data

def urlopen_bytes(url: str) -> bytes:
    with urllib.request.urlopen(build_request(url), timeout=30) as r:
        return r.read()

def ensure_ephemeris(date, cache_dir, sources=DEFAULT_SOURCES,
                     fetch=urlopen_bytes) -> str:
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    name = brdc_filename(date)
    local = cache / name
    if local.is_file():
        return str(local)
    last_err = None
    for url in source_urls(date, sources):
        try:
            data = decompress(url.rsplit("/", 1)[-1], fetch(url))
            if not looks_like_rinex(data):
                # 200 OK but not RINEX (e.g. an auth/login or error page) --
                # skip it rather than poisoning the cache; try the next mirror.
                last_err = EphemerisError(f"non-RINEX response from {url}")
                continue
            local.write_bytes(data)
            return str(local)
        except Exception as e:      # try next mirror
            last_err = e
    raise EphemerisError(f"could not fetch ephemeris for {date}: {last_err}")
