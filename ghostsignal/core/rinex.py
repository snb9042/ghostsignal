from __future__ import annotations
import datetime, gzip, urllib.request
from pathlib import Path

class EphemerisError(Exception):
    pass

# Mirror bases. CDDIS needs Earthdata auth; BKG/IGS mirrors are no-auth.
DEFAULT_SOURCES = [
    "https://igs.bkg.bund.de/root_ftp/IGS/BRDC/{yyyy}/{ddd}/",
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

def decompress(name: str, data: bytes) -> bytes:
    """Decompress .gz files; plain files returned as-is.

    Only .gz (gzip) decompression is handled. Plain RINEX files are returned
    unchanged. .Z (compress) format is not supported.
    """
    if name.endswith(".gz"):
        return gzip.decompress(data)
    return data

def urlopen_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as r:
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
            local.write_bytes(data)
            return str(local)
        except Exception as e:      # try next mirror
            last_err = e
    raise EphemerisError(f"could not fetch ephemeris for {date}: {last_err}")
