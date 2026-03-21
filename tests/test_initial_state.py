"""Tests for PresetMiddleware: state injection and merge behavior."""

import sys
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from preset_server import PresetMiddleware
from preset_server.processors import SessionProcessor


class StubProcessor:
    """Test processor that injects a fixed state dict."""

    def __init__(self, state: dict[str, Any]):
        self._state = state

    def process(
        self, app_name: str, agents_dir: Path, data: dict[str, Any]
    ) -> dict[str, Any]:
        merged = {**self._state, **(data.get("state") or {})}
        data["state"] = merged
        return data


def _make_app(tmp_path: Path, processors: list[SessionProcessor]) -> FastAPI:
    """Create a FastAPI app with PresetMiddleware using the given processors."""
    app = FastAPI()

    @app.post("/apps/{app_name}/users/{user_id}/sessions")
    async def create_session(app_name: str, user_id: str, request: Request):
        body = await request.json()
        return JSONResponse(body)

    @app.get("/list-apps")
    async def list_apps():
        return JSONResponse(["app1"])

    app.add_middleware(PresetMiddleware, agents_dir=tmp_path, processors=processors)
    return app


class TestPresetMiddleware:
    """Verify PresetMiddleware correctly injects and merges state."""

    @pytest.mark.asyncio
    async def test_injects_state(self, tmp_path):
        """Processor-defined state appears in the forwarded request body."""
        preset_state = {"time": "12:34 AM", "city": "Kyoto"}
        app = _make_app(tmp_path, [StubProcessor(preset_state)])

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/apps/myapp/users/user1/sessions", json={},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["state"]["time"] == "12:34 AM"
        assert data["state"]["city"] == "Kyoto"

    @pytest.mark.asyncio
    async def test_client_state_takes_precedence(self, tmp_path):
        """Client-supplied state overrides preset state on conflict."""
        preset_state = {"time": "12:34 AM", "city": "Kyoto"}
        app = _make_app(tmp_path, [StubProcessor(preset_state)])

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post(
                "/apps/myapp/users/user1/sessions",
                json={"state": {"city": "Osaka", "extra": "value"}},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["state"]["city"] == "Osaka"
        assert data["state"]["time"] == "12:34 AM"
        assert data["state"]["extra"] == "value"

    @pytest.mark.asyncio
    async def test_ignores_non_session_routes(self, tmp_path):
        """Non-session routes pass through unmodified."""
        app = _make_app(tmp_path, [StubProcessor({"x": 1})])

        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/list-apps")

        assert resp.status_code == 200
        assert resp.json() == ["app1"]
