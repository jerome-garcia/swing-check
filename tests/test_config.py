import pytest

from swingcheck.config import load_config


def test_defaults_load():
    config = load_config()
    assert config["golfer"]["handedness"] in ("right", "left")
    assert "address" in config["analyzers"]


def test_override_merges(tmp_path):
    override = tmp_path / "o.toml"
    override.write_text("[analyzers.fo_impact]\nhips_shift_min = 0.2\n")
    config = load_config(override)
    assert config["analyzers"]["fo_impact"]["hips_shift_min"] == 0.2
    # Sibling keys survive the merge.
    assert config["analyzers"]["fo_impact"]["head_behind_max"] == 0.60 and "address" in config["analyzers"]


def test_unknown_key_rejected(tmp_path):
    override = tmp_path / "o.toml"
    override.write_text("[analyzers.fo_impact]\nhips_shift = 0.2\n")
    with pytest.raises(KeyError, match="hips_shift"):
        load_config(override)
