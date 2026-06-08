"""Принятие вызова на бой."""

from __future__ import annotations

import time

from telegram import Update
from telegram.ext import ContextTypes

from game import db
from game.models import BattleState
from game.keyboards import loh_confirm_keyboard
from game.fight_confirm import fight_warning_text, needs_fight_warning
from handlers.battle_start import start_battle
from handlers.utils import display_name


async def on_fight_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return

    parts = query.data.split(":")
    if len(parts) < 3:
        return
    action = parts[1]
    try:
        challenge_id = int(parts[2])
    except ValueError:
        return

    chat = query.message.chat if query.message else None
    if not chat:
        return
    chat_id = chat.id
    user_id = query.from_user.id

    ch = db.get_challenge_by_id(challenge_id)
    if not ch or ch["chat_id"] != chat_id:
        await query.answer()
        await query.edit_message_text("Вызов устарел или отменён.")
        return

    if time.time() > ch["expires_at"]:
        db.delete_challenge_by_id(challenge_id)
        db.clear_pending_loh_for_challenge(challenge_id)
        await query.answer()
        await query.edit_message_text("Вызов истёк.")
        return

    challenger_id = ch["challenger_id"]
    target_id = ch["target_id"]

    if action == "decline":
        if target_id and user_id not in (challenger_id, target_id):
            await query.answer(
                "Личный вызов может отклонить только вызывающий или адресат.",
                show_alert=True,
            )
            return
        db.delete_challenge_by_id(challenge_id)
        db.clear_pending_loh_for_challenge(challenge_id)
        who = (
            "Вызов отклонён вызывающим."
            if user_id == challenger_id
            else "Вызов отклонён."
        )
        await query.answer()
        await query.edit_message_text(who)
        return

    if user_id == challenger_id:
        await query.answer("Нельзя принять свой вызов.", show_alert=True)
        return

    if target_id and user_id != target_id:
        await query.answer("Этот вызов не для вас.", show_alert=True)
        return

    if action in ("accept", "loh_ok"):
        if action == "accept":
            accepter = db.get_or_create_player(
                chat_id, user_id, display_name(query.from_user)
            )
            if needs_fight_warning(accepter.v_tier):
                db.set_pending_loh(chat_id, user_id, challenge_id)
                await query.answer()
                await query.edit_message_text(
                    fight_warning_text(accepter.v_tier),
                    reply_markup=loh_confirm_keyboard(challenge_id),
                )
                return
        await query.answer()
        await start_battle(
            context, chat_id, challenger_id, user_id, query.message.message_id
        )
        db.delete_challenge_by_id(challenge_id)
        db.clear_pending_loh_for_challenge(challenge_id)
