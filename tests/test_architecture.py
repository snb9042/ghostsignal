import pathlib, re

PURE = ["core", "backends", "sdr", "headless"]

def test_no_pyqt_in_pure_packages():
    root = pathlib.Path(__file__).resolve().parent.parent / "ghostsignal"
    offenders = []
    for pkg in PURE:
        for py in (root / pkg).rglob("*.py"):
            text = py.read_text(encoding="utf-8")
            if re.search(r"^\s*(import|from)\s+PyQt6", text, re.M):
                offenders.append(str(py))
    assert offenders == [], f"PyQt6 imported in pure packages: {offenders}"
