"""Click CLI command for starting the preset-enhanced adk web server."""

from __future__ import annotations

import atexit
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import click
import uvicorn
from fastapi import FastAPI

from google.adk.cli.fast_api import get_fast_api_app
from google.adk.cli.utils import logs

from preset_server.middleware import PresetMiddleware
from preset_server.processors import InitialStateProcessor
from preset_server.promote import cleanup_auto_generated, generate_alias_dirs

LOG_LEVELS = click.Choice(
    ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    case_sensitive=False,
)


@click.command()
@click.argument(
    "agents_dir",
    type=click.Path(exists=True, dir_okay=True, file_okay=False, resolve_path=True),
    default=os.getcwd,
)
@click.option("--host", type=str, default="127.0.0.1", show_default=True, help="Binding host.")
@click.option("--port", type=int, default=8000, help="Server port.")
@click.option("--allow_origins", multiple=True, help="Allowed CORS origins.")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Enable verbose (DEBUG) logging.")
@click.option("--log_level", type=LOG_LEVELS, default="INFO", help="Logging level.")
@click.option("--trace_to_cloud", is_flag=True, default=False, help="Enable cloud trace for telemetry.")
@click.option("--otel_to_cloud", is_flag=True, default=False, help="Write OTel data to Google Cloud.")
@click.option("--reload/--no-reload", default=True, help="Enable auto-reload.")
@click.option("--a2a", is_flag=True, default=False, help="Enable A2A endpoint.")
@click.option("--reload_agents", is_flag=True, default=False, help="Enable live reload for agent changes.")
@click.option("--eval_storage_uri", type=str, default=None, help="Evals storage URI (e.g. gs://bucket).")
@click.option("--extra_plugins", multiple=True, help="Extra plugin classes or instances.")
@click.option("--url_prefix", type=str, default=None, help="URL path prefix for reverse proxy.")
@click.option("--session_service_uri", default=None, help="Session service URI.")
@click.option("--artifact_service_uri", type=str, default=None, help="Artifact service URI.")
@click.option("--memory_service_uri", type=str, default=None, help="Memory service URI.")
@click.option("--use_local_storage/--no_use_local_storage", default=True, show_default=True, help="Use local .adk storage.")
@click.option("--logo-text", type=str, default=None, help="Logo text in web UI.")
@click.option("--logo-image-url", type=str, default=None, help="Logo image URL in web UI.")
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
    """Start a FastAPI server with Web UI for agents (with preset support).

    AGENTS_DIR: Directory of agents where each subdirectory is a single
    agent containing at least __init__.py and agent.py files.

    \b
    Examples:
      python -m preset_server path/to/agents_dir
      python -m preset_server . --port 8080 --no-preset
    """
    if verbose and log_level == "INFO":
        log_level = "DEBUG"

    logs.setup_adk_logger(getattr(logging, log_level.upper()))

    agents_dir_path = Path(agents_dir).resolve()

    # --- Promote agents: generate / clean up alias directories ---
    cleanup_auto_generated(agents_dir_path)
    generated = generate_alias_dirs(agents_dir_path)
    if generated:
        names = [d.name for d in generated]
        click.secho(f"promote: generated aliases: {', '.join(names)}", fg="cyan")
    atexit.register(cleanup_auto_generated, agents_dir_path)

    # --- Lifespan ---
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

    # --- Build FastAPI app ---
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

    # --- Register preset middleware ---
    if preset:
        processors = [InitialStateProcessor()]
        app.add_middleware(
            PresetMiddleware,
            agents_dir=agents_dir_path,
            processors=processors,
        )
        click.secho(
            "PresetMiddleware: injecting preset state into POST /apps/*/users/*/sessions",
            fg="cyan",
        )

    # --- Run server ---
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        reload=reload,
    )
    server = uvicorn.Server(config)
    server.run()
