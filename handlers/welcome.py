"""Приветствие при добавлении бота в группу."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatMemberStatus, ChatType
from telegram.ext import ContextTypes, filters

from game import db

logger = logging.getLogger(__name__)

GROUP_WELCOME_TEXT = (
    "Вас приветствует бот Глаз Твердыни!\n\n"
    "[ 📋 ] Перед использованием бота, просим вас подписаться на основную "
    "группу его создателей для дальнейших новостях о обновлениях и патчах, "
    "а также правильно распределить /op, /ststaff и /staff Владельцу группы "
    "над участниками!\n\n"
    "Для начала использования бота пропишите — /start\n\n"
    "[ ⚡ ] Официальная группа — https://t.me/soboyssomems"
)

_ABSENT_STATUSES = frozenset(
    {
        ChatMemberStatus.LEFT,
        ChatMemberStatus.BANNED,
    }
)


def _bot_is_present(status: str, *, is_member: bool = True) -> bool:
    if status == ChatMemberStatus.RESTRICTED:
        return is_member
    return status in (
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
    )


def _should_send_group_welcome(old_status: str, new_status: str, *, is_member: bool) -> bool:
    was_absent = old_status in _ABSENT_STATUSES
    now_present = _bot_is_present(new_status, is_member=is_member)

    if was_absent and now_present:
        return True

    if (
        new_status == ChatMemberStatus.ADMINISTRATOR
        and old_status != ChatMemberStatus.ADMINISTRATOR
        and now_present
    ):
        return True

    return False


async def _send_group_welcome(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, *, reason: str
) -> None:
    if db.chat_welcome_was_sent(chat_id):
        return
    try:
        await context.bot.send_message(chat_id=chat_id, text=GROUP_WELCOME_TEXT)
        db.mark_chat_welcome_sent(chat_id)
        logger.info("Приветствие отправлено в чат %s (%s)", chat_id, reason)
    except Exception:
        logger.exception("Не удалось отправить приветствие в чат %s", chat_id)


def _sync_bot_group_membership(
    chat_id: int, old_status: str, new_status: str, *, is_member: bool
) -> None:
    if _bot_is_present(new_status, is_member=is_member):
        db.register_bot_group(chat_id)
    elif new_status in _ABSENT_STATUSES:
        db.unregister_bot_group(chat_id)


async def on_bot_added_to_group(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    member = update.my_chat_member
    if not member:
        return

    chat = member.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return

    if member.new_chat_member.user.id != context.bot.id:
        return

    old_status = member.old_chat_member.status
    new_status = member.new_chat_member.status
    is_member = getattr(member.new_chat_member, "is_member", True)

    _sync_bot_group_membership(
        chat.id, old_status, new_status, is_member=is_member
    )

    if not _should_send_group_welcome(old_status, new_status, is_member=is_member):
        return

    await _send_group_welcome(
        context,
        chat.id,
        reason=f"{old_status} → {new_status}",
    )


async def on_bot_joined_via_message(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = update.message
    if not message or not message.new_chat_members:
        return
    chat = message.chat
    if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return
    bot_id = context.bot.id
    if not any(user.id == bot_id for user in message.new_chat_members):
        return
    db.register_bot_group(chat.id)
    await _send_group_welcome(context, chat.id, reason="new_chat_members")
