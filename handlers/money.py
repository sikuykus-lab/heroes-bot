"""Переводы и денежные команды игроков."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from game import db
from game.currency import display_amount, from_display_units
from handlers.admin_auth import (
    parse_amount_and_reason,
    resolve_money_target,
)
from handlers.utils import display_name, require_group


async def cmd_dropmoney(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not update.message or not update.effective_user:
        return

    amount, reason = parse_amount_and_reason(context.args or [])
    if amount is None:
        await update.message.reply_text(
            "Использование: /dropmoney 700 — ответом на сообщение или с тегом получателя.\n"
            "Пример: /dropmoney 500 @username причина"
        )
        return

    chat_id = update.effective_chat.id
    actor = update.effective_user
    target = resolve_money_target(
        update.message, actor, chat_id, context.args or []
    )
    if not target:
        await update.message.reply_text(
            "Укажите получателя: ответьте на его сообщение или упомяните @username."
        )
        return
    if target.user_id == actor.id:
        await update.message.reply_text("Нельзя перевести деньги себе.")
        return

    sender = db.get_or_create_player(
        chat_id, actor.id, display_name(actor), actor.username or ""
    )
    recipient = db.get_or_create_player(
        chat_id, target.user_id, target.name
    )
    cur = db.get_chat_currency(chat_id)
    charge = from_display_units(cur, amount)
    if charge <= 0:
        await update.message.reply_text("Сумма слишком мала для текущей валюты чата.")
        return
    if sender.coins < charge:
        await update.message.reply_text(
            f"Недостаточно средств. Баланс: {display_amount(cur, sender.coins)}."
        )
        return

    sender.coins -= charge
    recipient.coins += charge
    db.save_player(sender)
    db.save_player(recipient)

    reason_line = f"\nПричина: {reason}" if reason else ""
    await update.message.reply_text(
        f"{display_name(actor)} → {target.name}: {display_amount(cur, charge)}.\n"
        f"Ваш баланс: {display_amount(cur, sender.coins)}.\n"
        f"Баланс {target.name}: {display_amount(cur, recipient.coins)}."
        f"{reason_line}"
    )
