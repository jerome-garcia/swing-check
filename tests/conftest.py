"""Tests run on the defaults only: your own config/local.toml (say, face-on switched on)
mustn't change what they expect. Set here, before any test module loads its config."""

from pathlib import Path

from swingcheck import config

config.LOCAL_CONFIG = Path(__file__).parent / "no-local-config.toml"  # never created
