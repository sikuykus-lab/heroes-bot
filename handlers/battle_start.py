"""Старт боя."""

from __future__ import annotations

import time

from telegram.ext import ContextTypes

from game import db
from game import battle_engine
from game.characters import resolve_battle_character
from game.models import BattleState
from game.keyboards import battle_keyboard
from handlers.battle_messages import delete_message_safe, replace_battle_message
from handlers.battle_ui import format_battle_message


async def start_battle(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    p1_id: int,
    p2_id: int,
    challenge_message_id: int,
) -> None:
    if db.battles_limit_reached(chat_id):
        limit = db.get_max_active_battles(chat_id)
        await context.bot.edit_message_text(
            f"Уже {limit} активных боя в чате.",
            chat_id=chat_id,
            message_id=challenge_message_id,
        )
        return

    p1 = db.get_or_create_player(chat_id, p1_id)
    p2 = db.get_or_create_player(chat_id, p2_id)

    state = BattleState(
        battle_id=0,
        chat_id=chat_id,
        p1_id=p1_id,
        p2_id=p2_id,
        turn_user_id=p1_id,
        p1_character=resolve_battle_character(p1.v_tier, p1.active_character),
        p2_character=resolve_battle_character(p2.v_tier, p2.active_character),
        last_turn_report=None,
        last_activity_at=time.time(),
    )
    battle_id = db.create_battle(chat_id, p1_id, p2_id, state)
    state.battle_id = battle_id
    battle_engine.begin_turn(state)

    from game.battle_mimic import init_mimic_for_battle

    mimic_lines = init_mimic_for_battle(state)
    text = format_battle_message(state, p1, p2)
    if mimic_lines:
        text += "\n\n" + "\n".join(mimic_lines)
    kb = battle_keyboard(state, p1_id, p1)
    await replace_battle_message(
        context.bot, chat_id, state, text, reply_markup=kb
    )
    await delete_message_safe(context.bot, chat_id, challenge_message_id)
    db.save_battle(battle_id, chat_id, p1_id, p2_id, state)
