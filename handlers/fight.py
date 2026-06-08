"""Вызов на бой."""

from __future__ import annotations

import time

from telegram import Update
from telegram.ext import ContextTypes

from game import db
from game.config import (
    CHALLENGE_TIMEOUT_OPEN_SEC,
    CHALLENGE_TIMEOUT_TARGET_SEC,
)
from game.keyboards import challenge_keyboard
from handlers.challenge_timer import schedule_challenge_expiry
from handlers.utils import display_name, is_fight_text, message_mentions_bot, require_group


async def handle_fight_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    message = update.message
    if not message:
        return

    text = message.text or message.caption or ""
    bot = context.bot
    bot_user = await bot.get_me()
    mentioned = message_mentions_bot(message, bot_user.username or "")
    is_cmd = message.text and message.text.strip().startswith("/fight")
    if not is_fight_text(text) and not is_cmd and not mentioned:
        return
    if is_cmd or mentioned:
        if "бой" not in text.lower() and not is_cmd:
            return

    chat_id = message.chat_id
    challenger = message.from_user
    if not challenger:
        return

    if db.battles_limit_reached(chat_id):
        limit = db.get_max_active_battles(chat_id)
        await message.reply_text(
            f"В чате уже {limit} активных боя. "
            "Дождитесь завершения одного из них."
        )
        return

    if db.challenges_limit_reached(chat_id):
        limit = db.get_max_open_challenges(chat_id)
        await message.reply_text(
            f"В чате уже {limit} открытых вызова. "
            "Дождитесь принятия или истечения одного из них."
        )
        return

    target_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if target.is_bot:
            await message.reply_text("Нельзя вызвать бота.")
            return
        if target.id == challenger.id:
            await message.reply_text("Нельзя вызвать себя.")
            return
        target_id = target.id

    timeout_sec = (
        CHALLENGE_TIMEOUT_TARGET_SEC if target_id else CHALLENGE_TIMEOUT_OPEN_SEC
    )
    expires = time.time() + timeout_sec
    timeout_label = f"{int(timeout_sec)} сек"
    target_name = ""
    if target_id and message.reply_to_message:
        target_name = display_name(message.reply_to_message.from_user)

    ch_text = (
        f"⚔️ {display_name(challenger)} вызывает на бой"
        + (f" {target_name}!" if target_id else " (открытый вызов)!")
        + f"\n\n⏱ Принять: {timeout_label}."
        + "\n\nПеред боем загляните в /shop (Магазин)."
    )
    sent = await message.reply_text(
        ch_text,
        reply_markup=challenge_keyboard(0, bool(target_id)),
    )
    cid = db.create_challenge(
        chat_id, challenger.id, target_id, sent.message_id, expires
    )
    await sent.edit_reply_markup(
        reply_markup=challenge_keyboard(cid, bool(target_id))
    )
    schedule_challenge_expiry(
        context,
        chat_id=chat_id,
        challenge_id=cid,
        message_id=sent.message_id,
        timeout_sec=timeout_sec,
    )
