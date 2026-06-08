"""Права администратора бота в чате."""

from __future__ import annotations

from telegram import Message, Update, User
from telegram.constants import ChatMemberStatus

from game import db
from handlers.utils import display_name


async def is_chat_creator(update: Update, user_id: int | None = None) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    uid = user_id if user_id is not None else user.id
    try:
        member = await update.get_bot().get_chat_member(chat.id, uid)
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False


async def is_bot_admin(update: Update, user_id: int | None = None) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    uid = user_id if user_id is not None else user.id
    if await is_chat_creator(update, uid):
        return True
    return db.is_bot_admin_in_db(chat.id, uid)


async def is_bot_senior_staff(update: Update, user_id: int | None = None) -> bool:
    """Старший staff или полный админ бота."""
    if await is_bot_admin(update, user_id):
        return True
    chat = update.effective_chat
    if not chat:
        return False
    uid = user_id if user_id is not None else update.effective_user.id
    if not uid:
        return False
    return db.is_bot_senior_staff_in_db(chat.id, uid)


async def is_bot_staff(update: Update, user_id: int | None = None) -> bool:
    """Staff, старший staff или полный админ бота."""
    if await is_bot_senior_staff(update, user_id):
        return True
    chat = update.effective_chat
    if not chat:
        return False
    uid = user_id if user_id is not None else update.effective_user.id
    if not uid:
        return False
    return db.is_bot_staff_in_db(chat.id, uid)


async def require_bot_admin(update: Update) -> bool:
    if not await is_bot_admin(update):
        if update.message:
            await update.message.reply_text("Нет прав администратора бота.")
        elif update.callback_query:
            await update.callback_query.answer(
                "Нет прав администратора бота.", show_alert=True
            )
        return False
    return True


async def require_bot_staff(update: Update) -> bool:
    if not await is_bot_staff(update):
        if update.message:
            await update.message.reply_text(
                "Нет прав staff. Доступ: /rv24, /cancelcalls."
            )
        elif update.callback_query:
            await update.callback_query.answer(
                "Нет прав staff.", show_alert=True
            )
        return False
    return True


async def require_cancel_fights(update: Update) -> bool:
    """Админ бота или старший staff."""
    if await is_bot_senior_staff(update):
        return True
    if update.message:
        await update.message.reply_text(
            "Нет прав. /cancelfights — админ бота или старший staff."
        )
    elif update.callback_query:
        await update.callback_query.answer(
            "Нет прав. /cancelfights — админ или старший staff.",
            show_alert=True,
        )
    return False


def resolve_mentioned_users(message: Message) -> list[User]:
    """Пользователи из reply и text_mention (без дубликатов)."""
    seen: set[int] = set()
    out: list[User] = []

    def add(user: User | None) -> None:
        if user and not user.is_bot and user.id not in seen:
            seen.add(user.id)
            out.append(user)

    if message.reply_to_message and message.reply_to_message.from_user:
        add(message.reply_to_message.from_user)
    for ent in message.entities or []:
        if ent.type == "text_mention" and ent.user:
            add(ent.user)
    return out


def resolve_target_user(message: Message, actor: User) -> User | None:
    """Цель: reply, text_mention или сам автор."""
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        if not target.is_bot:
            return target
    for ent in message.entities or []:
        if ent.type == "text_mention" and ent.user and not ent.user.is_bot:
            return ent.user
    return actor


def parse_positive_amount(args: list[str]) -> int | None:
    for part in args:
        cleaned = part.strip().lstrip("+")
        if cleaned.isdigit():
            val = int(cleaned)
            if val > 0:
                return val
    return None


def parse_amount_and_reason(args: list[str]) -> tuple[int | None, str]:
    """Первое положительное число — сумма, остальное — причина."""
    amount: int | None = None
    amount_idx = -1
    for i, part in enumerate(args):
        cleaned = part.strip().lstrip("+")
        if cleaned.isdigit():
            val = int(cleaned)
            if val > 0:
                amount = val
                amount_idx = i
                break
    if amount is None:
        return None, ""
    reason = " ".join(args[amount_idx + 1 :]).strip()
    return amount, reason


def resolve_money_target(message, actor, chat_id: int, args: list[str]):  # noqa: ANN001
    """Цель перевода/штрафа: reply, text_mention или @username (без дефолта на автора)."""
    from dataclasses import dataclass

    from game import db

    @dataclass
    class _Target:
        user_id: int
        name: str

    if message.reply_to_message and message.reply_to_message.from_user:
        u = message.reply_to_message.from_user
        if not u.is_bot:
            return _Target(u.id, display_name(u))

    for ent in message.entities or []:
        if ent.type == "text_mention" and ent.user and not ent.user.is_bot:
            return _Target(ent.user.id, display_name(ent.user))

    for ent in message.entities or []:
        if ent.type == "mention" and message.text:
            mention = message.text[ent.offset : ent.offset + ent.length]
            uname = mention.lstrip("@")
            found = db.find_player_by_username(chat_id, uname)
            if found:
                return _Target(
                    found.user_id,
                    found.display_name or f"@{uname}",
                )

    for part in args:
        if part.startswith("@"):
            found = db.find_player_by_username(chat_id, part)
            if found:
                return _Target(
                    found.user_id,
                    found.display_name or part,
                )

    return None
