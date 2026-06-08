"""Inline-клавиатуры."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from game.characters import (
    action_disabled,
    battle_action_label,
    character_has_native_escape,
    get_actions_for_character,
)
from game.config import (
    PRICE_V,
    PRICE_V1,
    PRICE_V14BB,
    PRICE_V24_PAID,
    PRICE_VIRUS,
)
from game.models import BattleState, Player


def shop_keyboard(player: Player) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                "V24 бесплатно (5м)", callback_data="shop:v24_free"
            ),
            InlineKeyboardButton(
                f"V24 ({PRICE_V24_PAID} coin)", callback_data="shop:v24_paid"
            ),
        ],
        [InlineKeyboardButton(f"V ({PRICE_V} coin)", callback_data="shop:v")],
        [InlineKeyboardButton(f"V1 ({PRICE_V1} coin)", callback_data="shop:v1")],
        [
            InlineKeyboardButton(
                f"V14BB ({PRICE_V14BB} coin)", callback_data="shop:v14bb"
            ),
        ],
        [
            InlineKeyboardButton(
                f"Вирус ({PRICE_VIRUS})", callback_data="shop:virus"
            ),
        ],
    ]
    return InlineKeyboardMarkup(rows)


def beam_response_keyboard(state: BattleState) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Увернуться от луча",
                    callback_data=f"battle:{state.battle_id}:beam_dodge",
                ),
                InlineKeyboardButton(
                    "Контратака",
                    callback_data=f"battle:{state.battle_id}:beam_counter",
                ),
            ]
        ]
    )


def challenge_keyboard(challenge_id: int, target_only: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Принять", callback_data=f"fight:accept:{challenge_id}"
                ),
                InlineKeyboardButton(
                    "Отказать", callback_data=f"fight:decline:{challenge_id}"
                ),
            ]
        ]
    )


def loh_confirm_keyboard(challenge_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Всё равно принять (я лох)",
                    callback_data=f"fight:loh_ok:{challenge_id}",
                ),
                InlineKeyboardButton(
                    "Отказать", callback_data=f"fight:decline:{challenge_id}"
                ),
            ]
        ]
    )


def battle_keyboard(
    state: BattleState,
    actor_id: int,
    player: Player,
) -> InlineKeyboardMarkup | None:
    if state.turn_user_id != actor_id:
        return None

    if state.beam_response_user_id == actor_id:
        return beam_response_keyboard(state)

    character = (
        state.p1_character if actor_id == state.p1_id else state.p2_character
    )
    status = state.status_for(actor_id)
    actions = get_actions_for_character(character)
    rows: list[list[InlineKeyboardButton]] = []

    row: list[InlineKeyboardButton] = []
    for act in actions:
        if act.kind == "passive_info":
            continue
        disabled = action_disabled(act.id, status, character)
        label = battle_action_label(act.id, act.label, status)
        if disabled:
            label = f"🔒 {label}"
        row.append(
            InlineKeyboardButton(
                label,
                callback_data=f"battle:{state.battle_id}:{act.id}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)

    items: list[InlineKeyboardButton] = []
    if player.virus_count > 0:
        items.append(
            InlineKeyboardButton(
                "Вирус", callback_data=f"battle:{state.battle_id}:item_virus"
            )
        )
    if items:
        rows.append(items)

    footer: list[InlineKeyboardButton] = [
        InlineKeyboardButton(
            "Сдаться", callback_data=f"battle:{state.battle_id}:surrender"
        ),
    ]
    if not character_has_native_escape(character):
        footer.insert(
            0,
            InlineKeyboardButton(
                "Побег", callback_data=f"battle:{state.battle_id}:battle_escape"
            ),
        )
    rows.append(footer)
    return InlineKeyboardMarkup(rows)
