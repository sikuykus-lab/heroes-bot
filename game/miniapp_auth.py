"""Проверка Telegram Web App initData и подписи chat_id."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign_chat_token(chat_id: int, bot_token: str) -> str:
    digest = hmac.new(
        _secret_key(bot_token),
        f"shop:{chat_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def verify_chat_token(chat_id: int, token: str, bot_token: str) -> bool:
    if not token:
        return False
    expected = sign_chat_token(chat_id, bot_token)
    return hmac.compare_digest(expected, token)


def validate_init_data(
    init_data: str, bot_token: str, *, max_age_sec: int = 86400
) -> dict[str, Any] | None:
    if not init_data:
        return None
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    computed = hmac.new(
        _secret_key(bot_token),
        data_check.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(computed, received_hash):
        return None
    try:
        auth_date = int(parsed.get("auth_date", "0"))
    except ValueError:
        return None
    if auth_date <= 0 or time.time() - auth_date > max_age_sec:
        return None
    user_raw = parsed.get("user")
    if not user_raw:
        return None
    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        return None
    if not user.get("id"):
        return None
    return {"user": user, "auth_date": auth_date}
