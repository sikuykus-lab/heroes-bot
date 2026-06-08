"""Читы админа в бою (всегда кубик 6)."""

from __future__ import annotations

from telegram import Bot
from telegram.constants import ChatMemberStatus

from game import db


async def cheats_applies(bot: Bot, chat_id: int, user_id: int) -> bool:
    if not db.get_chat_cheats_enabled(chat_id):
        return False
    if db.is_bot_admin_in_db(chat_id, user_id):
        return True
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False
