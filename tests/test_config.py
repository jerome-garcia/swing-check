import pytest

from swingcheck.config import load_config


def test_defaults_load():
    config = load_config()
    assert config["golfer"]["handedness"] in ("right", "left")
    assert "address" in config["analyzers"]


def test_override_merges(tmp_path):
    override = tmp_path / "o.toml"
    override.write_text("[analyzers.head_drift]\nmax_drift_away = 0.2\n")
    config = load_config(override)
    assert config["analyzers"]["head_drift"]["max_drift_away"] == 0.2
    # Sibling keys survive the merge.
    assert "weight_shift" in config["analyzers"]


def test_unknown_key_rejected(tmp_path):
    override = tmp_path / "o.toml"
    override.write_text("[analyzers.head_drift]\nmax_drift = 0.2\n")
    with pytest.raises(KeyError, match="max_drift"):
        load_config(override)
