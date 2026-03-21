"""Session request processors for the preset middleware.

Each processor transforms the session creation request body before it
reaches the downstream adk web application.  New features (e.g.
``initial_artifact``) can be added by implementing the
:class:`SessionProcessor` protocol and registering the instance in the
processor list.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional, Protocol, runtime_checkable

from adkx.config import find_preset_file, load_raw_yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class SessionProcessor(Protocol):
    """Protocol for session creation request processors.

    Implementations receive the parsed JSON body of a
    ``POST /apps/{app}/users/{user}/sessions`` request and return a
    (possibly modified) copy.
    """

    def process(
        self,
        app_name: str,
        agents_dir: Path,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform the session creation request body.

        Args:
            app_name: Agent application name extracted from the URL.
            agents_dir: Root directory containing agent subdirectories.
            data: Parsed JSON request body.

        Returns:
            The transformed request body.
        """
        ...


# ---------------------------------------------------------------------------
# InitialStateProcessor
# ---------------------------------------------------------------------------

class InitialStateProcessor:
    """Injects ``initial_state`` from preset.yaml into session requests.

    The preset state is merged *under* any state supplied by the client,
    so explicit client values always win.
    """

    def process(
        self,
        app_name: str,
        agents_dir: Path,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        state = self._load_initial_state(app_name, agents_dir)
        if state:
            merged = {**state, **(data.get("state") or {})}
            data["state"] = merged
            logger.info(
                "InitialStateProcessor: injected state for app=%s keys=%s",
                app_name,
                list(state.keys()),
            )
        return data

    @staticmethod
    def _load_initial_state(app_name: str, agents_dir: Path) -> Optional[dict]:
        agent_dir = agents_dir / app_name
        preset_path = find_preset_file(agent_dir)
        if preset_path is None:
            return None
        try:
            raw = load_raw_yaml(preset_path)
            return raw.get("initial_state") or None
        except Exception as e:
            logger.warning(
                "InitialStateProcessor: failed to load preset for %s: %s",
                app_name,
                e,
            )
            return None
