"""preset_server: adk web compatible server with preset support.

Provides automatic state injection and sub-agent promotion via
preset.yaml configuration files.
"""

from preset_server.config import find_preset_file, load_raw_yaml
from preset_server.middleware import PresetMiddleware
from preset_server.processors import InitialStateProcessor, SessionProcessor
from preset_server.promote import (
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
