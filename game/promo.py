"""Промокоды."""

from __future__ import annotations

from game import db
from game.config import PROMO_CODES
from game.currency import display_amount
from game.models import Player


class PromoResult:
    def __init__(self, ok: bool, message: str) -> None:
        self.ok = ok
        self.message = message


def redeem_promo(player: Player, code: str) -> PromoResult:
    key = code.strip().lower()
    if not key:
        return PromoResult(False, "Укажите код: /code промокод")
    amount = PROMO_CODES.get(key)
    if amount is None:
        return PromoResult(False, "Промокод не найден.")
    if db.promo_already_used(player.chat_id, player.user_id, key):
        return PromoResult(False, "Вы уже использовали этот промокод.")
    player.coins += amount
    db.mark_promo_used(player.chat_id, player.user_id, key)
    db.save_player(player)
    cur = db.get_chat_currency(player.chat_id)
    return PromoResult(
        True,
        f"Промокод принят! +{display_amount(cur, amount)} "
        f"(баланс: {display_amount(cur, player.coins)}).",
    )
