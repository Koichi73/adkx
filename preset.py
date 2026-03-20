from __future__ import annotations
import sys
from pathlib import Path
from typing import Any, Optional

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Preset file handling
# ---------------------------------------------------------------------------

PRESET_FILENAME = "preset.yaml"


def find_preset_file(agent_dir: Path) -> Optional[Path]:
    """Search for preset.yaml in .adk/ directory of the agent."""
    candidates = [
        agent_dir / ".adk" / PRESET_FILENAME,
        agent_dir / PRESET_FILENAME,
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def load_preset(path: Path, preset_name: Optional[str] = None) -> dict[str, Any]:
    """Load preset configuration from YAML file.

    Returns:
        dict with keys: 'state' (dict) and 'query' (str or None)
    """
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # If a named preset is requested, look in the presets section
    if preset_name:
        presets = data.get("presets", {})
        if preset_name not in presets:
            available = ", ".join(presets.keys()) if presets else "(none)"
            print(f"Error: Preset '{preset_name}' not found. Available: {available}")
            sys.exit(1)
        p = presets[preset_name]
        return {
            "state": p.get("state", {}),
            "query": p.get("query"),
        }

    # Default: use top-level initial_state and initial_query
    return {
        "state": data.get("initial_state", {}),
        "query": data.get("initial_query"),
    }
