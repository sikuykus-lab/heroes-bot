"""HTTP-сервер Mini App магазина (aiohttp)."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from aiohttp import web

from game import shop_api
from game.config import MINIAPP_HOST, MINIAPP_PORT
from game.miniapp_auth import validate_init_data, verify_chat_token

logger = logging.getLogger(__name__)

MINIAPP_DIR = Path(__file__).resolve().parent.parent / "miniapp"


def _init_data_from_request(request: web.Request) -> str | None:
    header = request.headers.get("X-Telegram-Init-Data")
    if header:
        return header
    return request.query.get("initData")


async def _auth_context(
    request: web.Request,
    bot_token: str,
    *,
    body: dict | None = None,
) -> tuple[dict, int, str] | web.Response:
    init_data = _init_data_from_request(request)
    if not init_data:
        return web.json_response({"ok": False, "message": "Нет initData."}, status=401)

    parsed = validate_init_data(init_data, bot_token)
    if not parsed:
        return web.json_response({"ok": False, "message": "Неверная подпись."}, status=403)

    try:
        chat_id = int(request.query.get("chat_id") or request.match_info.get("chat_id", ""))
    except (TypeError, ValueError):
        return web.json_response({"ok": False, "message": "Неверный chat_id."}, status=400)

    token = request.query.get("token") or ""
    if body is not None:
        token = body.get("token") or token

    if not verify_chat_token(chat_id, token, bot_token):
        return web.json_response({"ok": False, "message": "Неверный токен чата."}, status=403)

    user = parsed["user"]
    display_name = " ".join(
        x for x in (user.get("first_name"), user.get("last_name")) if x
    ).strip() or user.get("username") or ""
    return parsed, chat_id, display_name


async def handle_index(_request: web.Request) -> web.Response:
    index = MINIAPP_DIR / "index.html"
    return web.FileResponse(index)


async def handle_static(request: web.Request) -> web.Response:
    rel = request.match_info.get("path", "")
    if ".." in rel or rel.startswith("/"):
        raise web.HTTPNotFound()
    target = MINIAPP_DIR / rel
    if not target.is_file():
        raise web.HTTPNotFound()
    return web.FileResponse(target)


async def handle_shop_state(request: web.Request) -> web.Response:
    bot_token: str = request.app["bot_token"]
    ctx = await _auth_context(request, bot_token)
    if isinstance(ctx, web.Response):
        return ctx
    _parsed, chat_id, display_name = ctx
    user_id = int(_parsed["user"]["id"])
    data = shop_api.get_shop_state(chat_id, user_id, display_name)
    return web.json_response(data)


async def handle_purchase(request: web.Request) -> web.Response:
    bot_token: str = request.app["bot_token"]
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response({"ok": False, "message": "Неверный JSON."}, status=400)

    ctx = await _auth_context(request, bot_token, body=body)
    if isinstance(ctx, web.Response):
        return ctx
    parsed, chat_id, display_name = ctx
    user_id = int(parsed["user"]["id"])

    action = body.get("action")
    character = body.get("character")
    data = shop_api.execute_action(
        chat_id,
        user_id,
        action,
        display_name=display_name,
        character=character,
    )
    status = 200 if data.get("ok") else 400
    return web.json_response(data, status=status)


def create_app(bot_token: str) -> web.Application:
    app = web.Application()
    app["bot_token"] = bot_token
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/shop", handle_shop_state)
    app.router.add_post("/api/purchase", handle_purchase)
    app.router.add_get("/assets/{path:.+}", handle_static)
    return app


async def start_miniapp_server(bot_token: str) -> web.AppRunner:
    app = create_app(bot_token)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, MINIAPP_HOST, MINIAPP_PORT)
    await site.start()
    logger.info("Mini App server on http://%s:%s", MINIAPP_HOST, MINIAPP_PORT)
    return runner
