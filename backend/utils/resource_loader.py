"""
Utility helpers for loading configuration and resource files with caching.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

_RESOURCE_CACHE: Dict[Path, Any] = {}


def load_json_resource(file_path: Path, default: Any) -> Any:
    """
    Load a JSON file from disk with basic caching and defensive fallbacks.

    Args:
        file_path: Absolute path to the JSON resource.
        default: Default value to return if the file is missing or invalid.

    Returns:
        Parsed JSON content or a deep copy of the default value.
    """
    if file_path in _RESOURCE_CACHE:
        return deepcopy(_RESOURCE_CACHE[file_path])

    try:
        with file_path.open('r', encoding='utf-8') as handle:
            data = json.load(handle)
            _RESOURCE_CACHE[file_path] = data
            return deepcopy(data)
    except FileNotFoundError:
        print(f"Resource file missing: {file_path}. Using default.")
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in {file_path}: {exc}. Using default.")
    except Exception as exc:
        print(f"Unexpected error loading {file_path}: {exc}. Using default.")

    _RESOURCE_CACHE[file_path] = default
    return deepcopy(default)
