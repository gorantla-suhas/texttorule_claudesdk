"""Config loader tests."""

from app.tools.config_loader import load_config, reload_configs


def test_load_action_catalog():
    cfg = load_config("action_catalog")
    assert "actions" in cfg
    types = {a["type"] for a in cfg["actions"]}
    assert "data_bonus" in types
    assert "subscribe" in types


def test_load_clients():
    cfg = load_config("clients")
    assert "omantel" in cfg["clients"]
    assert "airtel" in cfg["clients"]


def test_reload_clears_cache():
    cfg1 = load_config("clients")
    cfg2 = load_config("clients")
    assert cfg1 is cfg2  # cached
    reload_configs()
    cfg3 = load_config("clients")
    assert cfg1 is not cfg3  # rebuilt
