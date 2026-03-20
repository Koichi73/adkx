#!/usr/bin/env python3
"""preset_server.py: adk web 互換 CLI + preset state 自動注入ミドルウェア。

Usage:
    python preset_server.py .
    python preset_server.py . --port 8080
    python preset_server.py /path/to/agents --host 0.0.0.0 --port 8000

adk web と同じオプションをすべてサポートしつつ、
--preset フラグ（デフォルト有効）で PresetMiddleware を追加します。

各エージェントディレクトリの .adk/preset.yaml (または preset.yaml) に
initial_state を書いておくと、「New Session」ボタンを押した際に
自動的にその state が注入されます。

preset.yaml の例:
    initial_state:
      user_name: "田中太郎"
      language: "ja"
      mode: "debug"
"""

from __future__ import annotations

import functools
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import click
import uvicorn
from fastapi import FastAPI

from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.utils import logs

from preset import find_preset_file, load_preset

logger = logging.getLogger(__name__)

LOG_LEVELS = click.Choice(
    ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    case_sensitive=False,
)

SESSION_PATH = re.compile(r"^/apps/([^/]+)/users/[^/]+/sessions$")


# ---------------------------------------------------------------------------
# PresetMiddleware (ASGI)
# ---------------------------------------------------------------------------

class PresetMiddleware:
    """POST /apps/{app}/users/{user}/sessions に preset state を透過注入する純粋 ASGI ミドルウェア。"""

    def __init__(self, app, agents_dir: Path):
        self.app = app
        self.agents_dir = agents_dir

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")
        m = SESSION_PATH.match(path)

        if method == "POST" and m:
            app_name = m.group(1)
            preset = self._load_preset(app_name)
            if preset and preset.get("state"):
                body_parts = []
                while True:
                    message = await receive()
                    body_parts.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
                body = b"".join(body_parts)

                data = json.loads(body) if body else {}
                merged = {**preset["state"], **(data.get("state") or {})}
                data["state"] = merged
                new_body = json.dumps(data).encode()

                new_headers = []
                seen_ct = False
                seen_cl = False
                for key, value in scope.get("headers", []):
                    lower_key = key.lower()
                    if lower_key == b"content-length":
                        new_headers.append((b"content-length", str(len(new_body)).encode()))
                        seen_cl = True
                    elif lower_key == b"content-type":
                        new_headers.append((b"content-type", b"application/json"))
                        seen_ct = True
                    else:
                        new_headers.append((key, value))
                if not seen_ct:
                    new_headers.append((b"content-type", b"application/json"))
                if not seen_cl:
                    new_headers.append((b"content-length", str(len(new_body)).encode()))
                scope["headers"] = new_headers

                body_sent = False

                async def new_receive():
                    nonlocal body_sent
                    if not body_sent:
                        body_sent = True
                        return {"type": "http.request", "body": new_body, "more_body": False}
                    return await receive()

                logger.info(
                    "PresetMiddleware: injected state for app=%s keys=%s",
                    app_name,
                    list(preset["state"].keys()),
                )
                await self.app(scope, new_receive, send)
                return

        await self.app(scope, receive, send)

    def _load_preset(self, app_name: str) -> Optional[dict]:
        agent_dir = self.agents_dir / app_name
        preset_path = find_preset_file(agent_dir)
        if preset_path is None:
            return None
        try:
            return load_preset(preset_path)
        except Exception as e:
            logger.warning("PresetMiddleware: failed to load preset for %s: %s", app_name, e)
            return None


# ---------------------------------------------------------------------------
# CLI (adk web 互換)
# ---------------------------------------------------------------------------

@click.command()
@click.argument(
    "agents_dir",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, resolve_path=True),
    default=os.getcwd,
)
@click.option("--host", type=str, default="127.0.0.1", show_default=True, help="The binding host of the server.")
@click.option("--port", type=int, default=8000, help="The port of the server.")
@click.option("--allow_origins", multiple=True, help="Origins to allow for CORS.")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable verbose (DEBUG) logging.")
@click.option("--log_level", type=LOG_LEVELS, default="INFO", help="Set the logging level.")
@click.option("--trace_to_cloud", is_flag=True, default=False, help="Enable cloud trace for telemetry.")
@click.option("--otel_to_cloud", is_flag=True, default=False, help="Write OTel data to Google Cloud.")
@click.option("--reload/--no-reload", default=True, help="Enable auto reload for server.")
@click.option("--a2a", is_flag=True, default=False, help="Enable A2A endpoint.")
@click.option("--reload_agents", is_flag=True, default=False, help="Enable live reload for agents changes.")
@click.option("--eval_storage_uri", type=str, default=None, help="Evals storage URI (e.g. gs://bucket).")
@click.option("--extra_plugins", multiple=True, help="Extra plugin classes or instances.")
@click.option("--url_prefix", type=str, default=None, help="URL path prefix for reverse proxy.")
@click.option("--session_service_uri", default=None, help="Session service URI.")
@click.option("--artifact_service_uri", type=str, default=None, help="Artifact service URI.")
@click.option("--memory_service_uri", type=str, default=None, help="Memory service URI.")
@click.option("--use_local_storage/--no_use_local_storage", default=True, show_default=True, help="Use local .adk storage.")
@click.option("--logo-text", type=str, default=None, help="Logo text in web UI.")
@click.option("--logo-image-url", type=str, default=None, help="Logo image URL in web UI.")
# --- preset 固有オプション ---
@click.option("--preset/--no-preset", default=True, show_default=True, help="Enable PresetMiddleware for auto state injection.")
def cli_preset_web(
    agents_dir: str,
    host: str,
    port: int,
    allow_origins: Optional[tuple[str, ...]],
    verbose: bool,
    log_level: str,
    trace_to_cloud: bool,
    otel_to_cloud: bool,
    reload: bool,
    a2a: bool,
    reload_agents: bool,
    eval_storage_uri: Optional[str],
    extra_plugins: Optional[tuple[str, ...]],
    url_prefix: Optional[str],
    session_service_uri: Optional[str],
    artifact_service_uri: Optional[str],
    memory_service_uri: Optional[str],
    use_local_storage: bool,
    logo_text: Optional[str],
    logo_image_url: Optional[str],
    preset: bool,
):
    """Starts a FastAPI server with Web UI for agents (with preset support).

    AGENTS_DIR: The directory of agents, where each subdirectory is a single
    agent, containing at least __init__.py and agent.py files.

    Example:

      python preset_server.py path/to/agents_dir
      python preset_server.py . --port 8080 --no-preset
    """
    if verbose and log_level == "INFO":
        log_level = "DEBUG"

    logs.setup_adk_logger(getattr(logging, log_level.upper()))

    agents_dir_path = Path(agents_dir).resolve()

    @asynccontextmanager
    async def _lifespan(app: FastAPI):
        preset_msg = " + PresetMiddleware" if preset else ""
        click.secho(
            f"""
+-----------------------------------------------------------------------------+
| ADK Web Server started{preset_msg:<53s}|
|                                                                             |
| For local testing, access at http://{host}:{port}.{" " * (29 - len(str(port)))}|
+-----------------------------------------------------------------------------+
""",
            fg="green",
        )
        yield
        click.secho(
            """
+-----------------------------------------------------------------------------+
| ADK Web Server shutting down...                                             |
+-----------------------------------------------------------------------------+
""",
            fg="green",
        )

    app = get_fast_api_app(
        agents_dir=agents_dir,
        session_service_uri=session_service_uri,
        artifact_service_uri=artifact_service_uri,
        memory_service_uri=memory_service_uri,
        use_local_storage=use_local_storage,
        eval_storage_uri=eval_storage_uri,
        allow_origins=list(allow_origins) if allow_origins else None,
        web=True,
        trace_to_cloud=trace_to_cloud,
        otel_to_cloud=otel_to_cloud,
        lifespan=_lifespan,
        a2a=a2a,
        host=host,
        port=port,
        url_prefix=url_prefix,
        reload_agents=reload_agents,
        extra_plugins=list(extra_plugins) if extra_plugins else None,
        logo_text=logo_text,
        logo_image_url=logo_image_url,
    )

    if preset:
        app.add_middleware(PresetMiddleware, agents_dir=agents_dir_path)
        click.secho(
            "PresetMiddleware: POST /apps/*/users/*/sessions に preset state を注入します",
            fg="cyan",
        )

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        reload=reload,
    )
    server = uvicorn.Server(config)
    server.run()


if __name__ == "__main__":
    cli_preset_web()
