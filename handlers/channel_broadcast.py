"""Рассылка постов канала во все группы бота."""

from __future__ import annotations

import asyncio
import logging

from telegram import Update
from telegram.error import BadRequest, Forbidden, RetryAfter
from telegram.ext import ContextTypes

from game import db
from game.config import CHANNEL_BROADCAST_USERNAME

logger = logging.getLogger(__name__)

FORWARD_BATCH_SIZE = 25
FORWARD_BATCH_DELAY_SEC = 1.0


async def on_channel_post(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message = update.channel_post
    if not message:
        return

    channel = message.chat
    username = (channel.username or "").lower()
    if username != CHANNEL_BROADCAST_USERNAME.lower():
        return

    targets = db.list_bot_group_chats()
    if not targets:
        logger.info("Новый пост в @%s — групп для рассылки нет", username)
        return

    forwarded = 0
    removed = 0
    failed = 0

    for index, chat_id in enumerate(targets):
        try:
            await context.bot.forward_message(
                chat_id=chat_id,
                from_chat_id=channel.id,
                message_id=message.message_id,
            )
            forwarded += 1
        except RetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 0.5)
            try:
                await context.bot.forward_message(
                    chat_id=chat_id,
                    from_chat_id=channel.id,
                    message_id=message.message_id,
                )
                forwarded += 1
            except Exception:
                failed += 1
                logger.exception(
                    "Повторная пересылка поста %s в чат %s не удалась",
                    message.message_id,
                    chat_id,
                )
        except Forbidden:
            db.unregister_bot_group(chat_id)
            removed += 1
        except BadRequest as exc:
            if "chat not found" in str(exc).lower():
                db.unregister_bot_group(chat_id)
                removed += 1
            else:
                failed += 1
                logger.warning(
                    "Не удалось переслать пост %s в чат %s: %s",
                    message.message_id,
                    chat_id,
                    exc,
                )
        except Exception:
            failed += 1
            logger.exception(
                "Ошибка пересылки поста %s в чат %s",
                message.message_id,
                chat_id,
            )

        if (index + 1) % FORWARD_BATCH_SIZE == 0:
            await asyncio.sleep(FORWARD_BATCH_DELAY_SEC)

    logger.info(
        "Пост @%s #%s: переслано %s, удалено чатов %s, ошибок %s",
        username,
        message.message_id,
        forwarded,
        removed,
        failed,
    )
