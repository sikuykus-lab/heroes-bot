"""Отправка/удаление сообщений боя в чате."""

from __future__ import annotations

import logging

from telegram import Bot, InlineKeyboardMarkup
from telegram.error import BadRequest, TelegramError

from game.models import BattleState

logger = logging.getLogger(__name__)


async def delete_message_safe(
    bot: Bot, chat_id: int, message_id: int | None
) -> None:
    if not message_id:
        return
    try:
        await bot.delete_message(chat_id=chat_id, message_id=message_id)
    except (BadRequest, TelegramError) as exc:
        logger.debug("Не удалось удалить сообщение %s: %s", message_id, exc)


async def replace_battle_message(
    bot: Bot,
    chat_id: int,
    state: BattleState,
    text: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Новое сообщение со статами; предыдущее удаляется для всех."""
    old_id = state.message_id
    msg = await bot.send_message(
        chat_id=chat_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode="HTML",
    )
    state.message_id = msg.message_id
    await delete_message_safe(bot, chat_id, old_id)


async def roll_battle_dice(
    bot: Bot, chat_id: int, state: BattleState, *, user_id: int | None = None
) -> int:
    """Кидает кубик; предыдущий кубик в чате удаляется."""
    if user_id is not None:
        from game.cheats import cheats_applies

        if await cheats_applies(bot, chat_id, user_id):
            await delete_message_safe(bot, chat_id, state.last_dice_message_id)
            await bot.send_message(chat_id=chat_id, text="🎲 Читы: выпало 6")
            return 6
    await delete_message_safe(bot, chat_id, state.last_dice_message_id)
    dice_msg = await bot.send_dice(chat_id=chat_id)
    state.last_dice_message_id = dice_msg.message_id
    return dice_msg.dice.value


async def cleanup_battle_messages(
    bot: Bot, chat_id: int, state: BattleState
) -> None:
    await delete_message_safe(bot, chat_id, state.last_dice_message_id)
    state.last_dice_message_id = None
