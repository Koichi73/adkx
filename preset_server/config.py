"""Preset YAML discovery and loading utilities."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

PRESET_FILENAME = "preset.yaml"


def find_preset_file(agent_dir: Path) -> Optional[Path]:
    """Search for preset.yaml in the agent directory.

    Checks .adk/ subdirectory first, then the agent root.

    Returns:
        Path to the preset file, or None if not found.
    """
    candidates = [
        agent_dir / ".adk" / PRESET_FILENAME,
        agent_dir / PRESET_FILENAME,
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def load_raw_yaml(path: Path) -> dict:
    """Load raw YAML content from a file.

    Returns:
        Parsed YAML as a dict (empty dict if file is empty).
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}
