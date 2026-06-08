"""Медиафайлы бота (голос, стикеры)."""

from __future__ import annotations

import logging

from telegram import Bot

from game.config import EXCUSE_VOICE_PATH

logger = logging.getLogger(__name__)

AURA_FARMING_CAPTION = "ЕБАААТЬ, СКОЛЬКО ЖЕ У НЕГО АУРЫ НАХУЙЙЙ"


async def send_excuse_voice(bot: Bot, chat_id: int) -> bool:
    path = EXCUSE_VOICE_PATH
    if not path.is_file():
        logger.warning("Excuse.ogg не найден: %s", path)
        return False
    with path.open("rb") as voice:
        await bot.send_voice(chat_id=chat_id, voice=voice)
    return True
