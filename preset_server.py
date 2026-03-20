#!/usr/bin/env python3
"""preset_server.py: adk web + ASGI ミドルウェアによる preset state 自動注入サーバー。

Usage:
    python preset_server.py .
    python preset_server.py . --port 8080
    python preset_server.py /path/to/agents --host 0.0.0.0 --port 8000

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

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Optional

from preset import find_preset_file, load_preset

logger = logging.getLogger(__name__)

SESSION_PATH = re.compile(r"^/apps/([^/]+)/users/[^/]+/sessions$")


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
                # 元のボディを全て読み取る
                body_parts = []
                while True:
                    message = await receive()
                    body_parts.append(message.get("body", b""))
                    if not message.get("more_body", False):
                        break
                body = b"".join(body_parts)

                data = json.loads(body) if body else {}
                # フロントエンドが渡した state があればそちらを優先（マージして上書き）
                merged = {**preset["state"], **(data.get("state") or {})}
                data["state"] = merged
                new_body = json.dumps(data).encode()

                # ヘッダーの content-length / content-type を更新
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
                    # ボディ送信後は元の receive に委譲（disconnect 検知用）
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="adk web + preset state 自動注入サーバー",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python preset_server.py .
  python preset_server.py /path/to/agents --port 8080
  python preset_server.py . --host 0.0.0.0 --session-service-uri sqlite:///sessions.db
        """,
    )
    parser.add_argument(
        "agents_dir",
        nargs="?",
        default=".",
        help="エージェントが入っているディレクトリ (default: .)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="ポート番号 (default: 8000)",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="ホスト (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--session-service-uri",
        default=None,
        help="セッションサービス URI (例: sqlite:///sessions.db)",
    )
    parser.add_argument(
        "--artifact-service-uri",
        default=None,
        help="アーティファクトサービス URI",
    )
    parser.add_argument(
        "--memory-service-uri",
        default=None,
        help="メモリサービス URI",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="ログレベル (default: INFO)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    agents_dir = Path(args.agents_dir).resolve()
    if not agents_dir.is_dir():
        print(f"Error: agents_dir '{agents_dir}' is not a directory.")
        raise SystemExit(1)

    from google.adk.cli.fast_api import get_fast_api_app
    import uvicorn

    app = get_fast_api_app(
        agents_dir=str(agents_dir),
        web=True,
        host=args.host,
        port=args.port,
        session_service_uri=args.session_service_uri,
        artifact_service_uri=args.artifact_service_uri,
        memory_service_uri=args.memory_service_uri,
    )
    app.add_middleware(PresetMiddleware, agents_dir=agents_dir)

    print(f"Starting preset_server at http://{args.host}:{args.port}")
    print(f"Agents dir: {agents_dir}")
    print("PresetMiddleware: POST /apps/*/users/*/sessions に preset state を注入します")
    print()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
