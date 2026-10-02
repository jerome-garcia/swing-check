"""Load config/default.toml, then overlay config/local.toml (or an explicit file)."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "default.toml"
LOCAL_CONFIG = PROJECT_ROOT / "config" / "local.toml"


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read(path: Path) -> dict[str, Any]:
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_config(override_path: Path | None = None) -> dict[str, Any]:
    """Defaults, then local.toml if present, then `override_path` if given.

    Unknown keys in an override are rejected so typos don't silently do nothing.
    """
    config = _read(DEFAULT_CONFIG)
    for path in (LOCAL_CONFIG, override_path):
        if path is not None and Path(path).exists():
            override = _read(Path(path))
            _check_keys(config, override, str(path))
            config = _deep_merge(config, override)
    return config


def _check_keys(base: dict[str, Any], override: dict[str, Any], source: str, prefix: str = "") -> None:
    for key, value in override.items():
        dotted = f"{prefix}{key}"
        if key not in base:
            raise KeyError(f"{source}: unknown config key '{dotted}'")
        if isinstance(value, dict) and isinstance(base[key], dict):
            _check_keys(base[key], value, source, dotted + ".")
