"""Стикеры Telegram."""

from __future__ import annotations

import logging

from telegram import Bot

from game.config import SOLDIER_BEAM_STICKER_SET

logger = logging.getLogger(__name__)


async def soldier_beam_sticker_file_id(bot: Bot, bot_data: dict) -> str | None:
    cached = bot_data.get("soldier_beam_sticker_id")
    if cached:
        return str(cached)
    try:
        sticker_set = await bot.get_sticker_set(SOLDIER_BEAM_STICKER_SET)
        if not sticker_set.stickers:
            return None
        file_id = sticker_set.stickers[0].file_id
        bot_data["soldier_beam_sticker_id"] = file_id
        return file_id
    except Exception:
        logger.exception("Не удалось загрузить стикер-пак %s", SOLDIER_BEAM_STICKER_SET)
        return None


async def send_soldier_beam_sticker(bot: Bot, chat_id: int, bot_data: dict) -> bool:
    return await send_soldier_beam_sticker_index(bot, chat_id, bot_data, 0)


async def send_soldier_beam_sticker_index(
    bot: Bot, chat_id: int, bot_data: dict, index: int
) -> bool:
    stickers = bot_data.get("soldier_beam_sticker_ids")
    if not stickers:
        try:
            sticker_set = await bot.get_sticker_set(SOLDIER_BEAM_STICKER_SET)
            stickers = [s.file_id for s in sticker_set.stickers]
            bot_data["soldier_beam_sticker_ids"] = stickers
        except Exception:
            logger.exception(
                "Не удалось загрузить стикер-пак %s", SOLDIER_BEAM_STICKER_SET
            )
            return False
    if not stickers or index < 0 or index >= len(stickers):
        return False
    await bot.send_sticker(chat_id=chat_id, sticker=stickers[index])
    return True
