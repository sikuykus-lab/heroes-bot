"""API-слой магазина для Mini App."""

from __future__ import annotations

import time
from typing import Any

from game import db
from game import shop as shop_logic
from game.characters import CHARACTER_NAMES
from game.config import (
    PRICE_V,
    PRICE_V1,
    PRICE_V14BB,
    PRICE_V24_PAID,
    PRICE_VIRUS,
    V24_FREE_COOLDOWN_SEC,
)
from game.currency import CURRENCY_RUBLES, currency_title, to_display_units
from game import db as _db_currency
from game.models import Player


def _v24_free_remaining_sec(player: Player) -> int:
    if not player.v24_last_free_at:
        return 0
    elapsed = time.time() - player.v24_last_free_at
    left = int(V24_FREE_COOLDOWN_SEC - elapsed)
    return max(0, left)


def _player_payload(player: Player) -> dict[str, Any]:
    return {
        "coins": player.coins,
        "v_tier": player.v_tier,
        "active_character": player.active_character,
        "active_character_name": CHARACTER_NAMES.get(
            player.active_character, player.active_character
        ),
        "v24_battles_left": player.v24_battles_left,
        "virus_count": player.virus_count,
    }


def _display_prices(chat_id: int) -> dict[str, int]:
    cur = _db_currency.get_chat_currency(chat_id)
    return {
        "v24_paid": to_display_units(cur, PRICE_V24_PAID),
        "v": to_display_units(cur, PRICE_V),
        "v1": to_display_units(cur, PRICE_V1),
        "v14bb": to_display_units(cur, PRICE_V14BB),
        "virus": to_display_units(cur, PRICE_VIRUS),
    }


def get_shop_state(
    chat_id: int, user_id: int, display_name: str = ""
) -> dict[str, Any]:
    player = db.get_or_create_player(chat_id, user_id, display_name)
    locked = db.has_active_battle(chat_id)
    cur = _db_currency.get_chat_currency(chat_id)
    return {
        "ok": True,
        "locked": locked,
        "lock_reason": "Магазин недоступен, пока идёт бой." if locked else None,
        "currency": cur,
        "currency_label": currency_title(cur),
        "currency_symbol": "₽" if cur == CURRENCY_RUBLES else "V",
        "player": {
            **_player_payload(player),
            "coins_display": to_display_units(cur, player.coins),
        },
        "prices": _display_prices(chat_id),
        "v24_free_remaining_sec": _v24_free_remaining_sec(player),
    }


def execute_action(
    chat_id: int,
    user_id: int,
    action: str,
    *,
    display_name: str = "",
    character: str | None = None,
) -> dict[str, Any]:
    if db.has_active_battle(chat_id):
        return {
            "ok": False,
            "message": "Магазин недоступен, пока идёт бой.",
        }

    if db.is_shop_item_blocked(chat_id, action):
        from game.shop_items import shop_item_label

        return {
            "ok": False,
            "message": f"«{shop_item_label(action)}» заблокирован админом.",
        }

    player = db.get_or_create_player(chat_id, user_id, display_name)
    handlers = {
        "v24_free": shop_logic.claim_v24_free,
        "v24_paid": shop_logic.buy_v24_paid,
        "v": shop_logic.buy_v,
        "v1": shop_logic.buy_v1,
        "v14bb": shop_logic.buy_v14bb,
        "virus": shop_logic.buy_virus,
    }

    fn = handlers.get(action)
    if not fn:
        return {"ok": False, "message": "Неизвестное действие."}
    result = fn(player)

    player = db.get_or_create_player(chat_id, user_id, player.display_name)
    payload = {
        "ok": result.ok,
        "message": result.message,
        "player": _player_payload(player),
        "v24_free_remaining_sec": _v24_free_remaining_sec(player),
    }
    return payload
