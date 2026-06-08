"""Покупки в магазине."""

from __future__ import annotations

import time

from game import db
from game.config import (
    PRICE_CHARACTER_SWITCH,
    PRICE_V,
    PRICE_V1,
    PRICE_V14BB,
    PRICE_V24_PAID,
    PRICE_VIRUS,
    V24_BATTLES,
    V24_FREE_COOLDOWN_SEC,
)
from game.achievements import on_v14bb_purchased
from game.characters import (
    CHARACTER_NAMES,
    apply_super_promotion,
    tier_allows_character,
)
from game.currency import display_amount, display_price
from game.models import Player


def _need_funds(player: Player, price_vcoin: int) -> str:
    cur = db.get_chat_currency(player.chat_id)
    return (
        f"Нужно {display_price(cur, price_vcoin)} "
        f"(у вас {display_amount(cur, player.coins)})."
    )


class ShopResult:
    def __init__(
        self,
        ok: bool,
        message: str,
        *,
        new_achievement=None,
    ) -> None:
        self.ok = ok
        self.message = message
        self.new_achievement = new_achievement


def buy_v24_paid(player: Player) -> ShopResult:
    if player.coins < PRICE_V24_PAID:
        return ShopResult(False, _need_funds(player, PRICE_V24_PAID))
    player.coins -= PRICE_V24_PAID
    player.v_tier = "v24"
    player.v24_battles_left = V24_BATTLES
    apply_super_promotion(player, roll=True)
    db.save_player(player)
    name = CHARACTER_NAMES.get(player.active_character, player.active_character)
    return ShopResult(
        True,
        f"V24 куплен! {V24_BATTLES} боя. Вам выпал: {name}.",
    )


def claim_v24_free(player: Player) -> ShopResult:
    now = time.time()
    if player.v24_last_free_at:
        elapsed = now - player.v24_last_free_at
        if elapsed < V24_FREE_COOLDOWN_SEC:
            left = int(V24_FREE_COOLDOWN_SEC - elapsed)
            return ShopResult(False, f"Бесплатный V24 через {left // 60}м {left % 60}с.")
    player.v24_last_free_at = now
    player.v_tier = "v24"
    player.v24_battles_left = V24_BATTLES
    apply_super_promotion(player, roll=True)
    db.save_player(player)
    name = CHARACTER_NAMES.get(player.active_character, player.active_character)
    return ShopResult(
        True,
        f"Бесплатный V24! {V24_BATTLES} боя. Вам выпал: {name}.",
    )


def buy_v(player: Player) -> ShopResult:
    if player.coins < PRICE_V:
        return ShopResult(False, _need_funds(player, PRICE_V))
    player.coins -= PRICE_V
    player.v_tier = "v"
    player.v24_battles_left = 0
    apply_super_promotion(player, roll=True)
    db.save_player(player)
    name = CHARACTER_NAMES.get(player.active_character, player.active_character)
    return ShopResult(True, f"V куплен! Вам выпал: {name}.")


def buy_v1(player: Player) -> ShopResult:
    if player.coins < PRICE_V1:
        return ShopResult(False, _need_funds(player, PRICE_V1))
    player.coins -= PRICE_V1
    player.v_tier = "v1"
    player.v24_battles_left = 0
    apply_super_promotion(player, roll=True)
    db.save_player(player)
    name = CHARACTER_NAMES.get(player.active_character, player.active_character)
    return ShopResult(True, f"V1 куплен! Вам выпал: {name}. Иммунитет к вирусу.")


def buy_v14bb(player: Player) -> ShopResult:
    if player.coins < PRICE_V14BB:
        return ShopResult(False, _need_funds(player, PRICE_V14BB))
    player.coins -= PRICE_V14BB
    player.v_tier = "v14bb"
    player.v24_battles_left = 0
    player.active_character = "loh_full"
    db.save_player(player)
    new_ach = on_v14bb_purchased(player.chat_id, player.user_id)
    return ShopResult(
        True,
        "V14BB куплен! Вы — Полный Лох. Только побег и сдача в бою.",
        new_achievement=new_ach,
    )


def buy_virus(player: Player) -> ShopResult:
    if player.coins < PRICE_VIRUS:
        return ShopResult(False, _need_funds(player, PRICE_VIRUS))
    player.coins -= PRICE_VIRUS
    player.virus_count += 1
    db.save_player(player)
    return ShopResult(True, f"Вирус в инвентаре ({player.virus_count}).")


def switch_character(player: Player, character: str) -> ShopResult:
    if player.v_tier not in ("v", "v1", "v24"):
        return ShopResult(False, "Смена персонажа доступна при активном V.")
    if not tier_allows_character(player.v_tier, character):
        return ShopResult(False, "Персонаж недоступен для вашего уровня V.")
    if player.active_character == character:
        return ShopResult(False, "Уже выбран этот персонаж.")
    if player.coins < PRICE_CHARACTER_SWITCH:
        cur = db.get_chat_currency(player.chat_id)
        return ShopResult(
            False,
            f"Смена стоит {display_price(cur, PRICE_CHARACTER_SWITCH)}.",
        )
    player.coins -= PRICE_CHARACTER_SWITCH
    player.active_character = character
    db.save_player(player)
    name = CHARACTER_NAMES.get(character, character)
    return ShopResult(
        True,
        f"Персонаж: {name} (списано {PRICE_CHARACTER_SWITCH} coin).",
    )
