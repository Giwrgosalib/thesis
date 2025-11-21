"""
Centralized configuration loader for the next-generation backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

import yaml


@dataclass
class NextGenConfig:
    """Dataclass wrapper to offer attribute-style access to nested configs."""

    raw: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def section(self, key: str) -> Dict[str, Any]:
        return self.raw.setdefault(key, {})


def load_config(config_path: Path | None = None) -> NextGenConfig:
    """
    Load YAML configuration with helpful defaults.

    Args:
        config_path: Optional override for the config path.

    Returns:
        NextGenConfig instance containing the parsed configuration.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parent / "nextgen_config.yml"

    if not config_path.exists():
        raise FileNotFoundError(f"Next-gen config file not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return NextGenConfig(raw=data)
