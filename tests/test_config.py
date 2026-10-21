from ghostsignal.config import ToolConfig

def test_override_wins(monkeypatch):
    c = ToolConfig(overrides={"gps": "/custom/gps-sdr-sim"})
    assert c.resolve_tool("gps") == "/custom/gps-sdr-sim"

def test_env_var_used(monkeypatch):
    monkeypatch.setenv("HACKRF_TRANSFER", "/env/hackrf_transfer")
    c = ToolConfig()
    assert c.resolve_tool("hackrf") == "/env/hackrf_transfer"

def test_default_bare_command(monkeypatch):
    monkeypatch.delenv("GPS_SDR_SIM", raising=False)
    c = ToolConfig()
    assert c.resolve_tool("gps") == "gps-sdr-sim"

def test_default_tool_keys():
    from ghostsignal.config import DEFAULT_TOOL_KEYS
    assert DEFAULT_TOOL_KEYS == {"gps", "galileo", "gnss_multi", "hackrf", "soapy"}
