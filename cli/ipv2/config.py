"""Layered configuration loading.

Priority (highest first):
1. CLI flag value passed in at call time
2. Environment variable (IPV2_BASE_URL, IPV2_TOKEN, IPV2_CONFIG_DIR)
3. Project config: ./.ipv2.yaml
4. User config: ~/.ipv2/config.yaml
5. Built-in defaults
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_BASE_URL = "https://investment-platform-v2-yt3vv5n7za-de.a.run.app"
DEFAULT_CONFIG_DIR = Path.home() / ".ipv2"


def _config_dir() -> Path:
    env = os.environ.get("IPV2_CONFIG_DIR")
    return Path(env) if env else DEFAULT_CONFIG_DIR


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _user_config() -> dict[str, Any]:
    return _load_yaml_file(_config_dir() / "config.yaml")


def _project_config() -> dict[str, Any]:
    return _load_yaml_file(Path(".ipv2.yaml"))


def resolve_base_url(flag_value: str | None = None) -> str:
    """Return the effective base URL from the config stack."""
    if flag_value:
        return flag_value.rstrip("/")
    env = os.environ.get("IPV2_BASE_URL")
    if env:
        return env.rstrip("/")
    project = _project_config().get("base_url")
    if project:
        return str(project).rstrip("/")
    user = _user_config().get("base_url")
    if user:
        return str(user).rstrip("/")
    return DEFAULT_BASE_URL


def config_dir() -> Path:
    """Return ~/.ipv2 (or IPV2_CONFIG_DIR override)."""
    return _config_dir()
