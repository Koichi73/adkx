"""ASGI middleware that applies session processors to session creation requests."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from adkx.processors import InitialStateProcessor, SessionProcessor

logger = logging.getLogger(__name__)

SESSION_PATH = re.compile(r"^/apps/([^/]+)/users/[^/]+/sessions$")


class PresetMiddleware:
    """ASGI middleware that intercepts session creation and applies processors.

    Intercepts ``POST /apps/{app}/users/{user}/sessions`` requests and
    runs each registered :class:`SessionProcessor` on the parsed JSON body
    before forwarding the (possibly modified) request downstream.

    Args:
        app: The ASGI application to wrap.
        agents_dir: Root directory containing agent subdirectories.
        processors: Ordered list of session processors to apply.
            Defaults to ``[InitialStateProcessor()]``.
    """

    def __init__(
        self,
        app,
        agents_dir: Path,
        processors: list[SessionProcessor] | None = None,
    ):
        self.app = app
        self.agents_dir = agents_dir
        self.processors: list[SessionProcessor] = processors or [
            InitialStateProcessor()
        ]

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        method = scope.get("method", "")
        m = SESSION_PATH.match(path)

        if method == "POST" and m:
            app_name = m.group(1)

            # Read the full request body
            body_parts: list[bytes] = []
            while True:
                message = await receive()
                body_parts.append(message.get("body", b""))
                if not message.get("more_body", False):
                    break
            body = b"".join(body_parts)

            data: dict = json.loads(body) if body else {}

            # Apply each processor in order
            for processor in self.processors:
                data = processor.process(app_name, self.agents_dir, data)

            new_body = json.dumps(data).encode()

            # Update headers (content-length / content-type)
            new_headers: list[tuple[bytes, bytes]] = []
            seen_ct = False
            seen_cl = False
            for key, value in scope.get("headers", []):
                lower_key = key.lower()
                if lower_key == b"content-length":
                    new_headers.append(
                        (b"content-length", str(len(new_body)).encode())
                    )
                    seen_cl = True
                elif lower_key == b"content-type":
                    new_headers.append((b"content-type", b"application/json"))
                    seen_ct = True
                else:
                    new_headers.append((key, value))
            if not seen_ct:
                new_headers.append((b"content-type", b"application/json"))
            if not seen_cl:
                new_headers.append(
                    (b"content-length", str(len(new_body)).encode())
                )
            scope["headers"] = new_headers

            body_sent = False

            async def new_receive():
                nonlocal body_sent
                if not body_sent:
                    body_sent = True
                    return {
                        "type": "http.request",
                        "body": new_body,
                        "more_body": False,
                    }
                return await receive()

            await self.app(scope, new_receive, send)
            return

        await self.app(scope, receive, send)
