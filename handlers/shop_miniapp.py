"""Кнопка и URL Mini App магазина."""

from __future__ import annotations

from urllib.parse import urlencode

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

from game.config import MINIAPP_ENABLED, SHOP_MINIAPP_URL
from game.miniapp_auth import sign_chat_token


def shop_webapp_url(chat_id: int, bot_token: str) -> str | None:
    if not MINIAPP_ENABLED or not SHOP_MINIAPP_URL:
        return None
    base = SHOP_MINIAPP_URL.rstrip("/")
    token = sign_chat_token(chat_id, bot_token)
    qs = urlencode({"chat_id": chat_id, "token": token})
    return f"{base}/?{qs}"


def shop_open_keyboard(chat_id: int, bot_token: str) -> InlineKeyboardMarkup | None:
    url = shop_webapp_url(chat_id, bot_token)
    if not url:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("🛒 Открыть магазин", web_app=WebAppInfo(url=url))]]
    )
