"""Общие утилиты handlers."""

from __future__ import annotations

from telegram import Update

from game import db


def display_name(user) -> str:
    parts = [user.first_name or "", user.last_name or ""]
    name = " ".join(p for p in parts if p).strip()
    return name or (user.username or "Игрок")


async def require_group(update: Update) -> bool:
    chat = update.effective_chat
    if chat.type not in ("group", "supergroup"):
        if update.message:
            await update.message.reply_text("Игра только в групповых чатах.")
        return False
    db.register_bot_group(chat.id)
    return True


def message_mentions_bot(message, bot_username: str) -> bool:
    if not message or not bot_username:
        return False
    uname = bot_username.lower().lstrip("@")
    for ent in message.entities or []:
        if ent.type == "mention":
            mention = message.text[ent.offset : ent.offset + ent.length].lstrip("@").lower()
            if mention == uname:
                return True
    return False


def is_fight_text(text: str | None) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return t in ("бой", "fight", "/fight") or t.startswith("/fight@")
