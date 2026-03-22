"""adkx: adk web compatible server with preset support.

Provides automatic state injection and sub-agent promotion via
preset.yaml configuration files.
"""

from importlib.metadata import version

from adkx.config import find_preset_file, load_raw_yaml
from adkx.middleware import PresetMiddleware
from adkx.processors import InitialStateProcessor, SessionProcessor
from adkx.promote import cleanup_auto_generated, generate_alias_dirs

__version__ = version("adkx")

__all__ = [
    "find_preset_file",
    "load_raw_yaml",
    "PresetMiddleware",
    "SessionProcessor",
    "InitialStateProcessor",
    "cleanup_auto_generated",
    "generate_alias_dirs",
]
