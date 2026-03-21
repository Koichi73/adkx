"""adkx: adk web compatible server with preset support.

Provides automatic state injection and sub-agent promotion via
preset.yaml configuration files.
"""

from adkx.config import find_preset_file, load_raw_yaml
from adkx.middleware import PresetMiddleware
from adkx.processors import InitialStateProcessor, SessionProcessor
from adkx.promote import (
    _AUTO_GENERATED_MARKER,
    cleanup_auto_generated,
    generate_alias_dirs,
)

__all__ = [
    "find_preset_file",
    "load_raw_yaml",
    "PresetMiddleware",
    "SessionProcessor",
    "InitialStateProcessor",
    "_AUTO_GENERATED_MARKER",
    "cleanup_auto_generated",
    "generate_alias_dirs",
]
