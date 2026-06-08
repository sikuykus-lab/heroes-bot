"""Автоотмена вызовов по таймеру."""

from __future__ import annotations

import logging

from telegram.ext import ContextTypes

from game import db

logger = logging.getLogger(__name__)


async def expire_challenge_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data if context.job else {}
    chat_id = data.get("chat_id")
    challenge_id = data.get("challenge_id")
    message_id = data.get("message_id")
    if chat_id is None or challenge_id is None or message_id is None:
        return

    ch = db.get_challenge_by_id(challenge_id)
    if not ch or ch["chat_id"] != chat_id:
        return

    db.delete_challenge_by_id(challenge_id)
    db.clear_pending_loh_for_challenge(challenge_id)

    try:
        await context.bot.edit_message_text(
            "Вызов истёк — никто не ответил.",
            chat_id=chat_id,
            message_id=message_id,
            reply_markup=None,
        )
    except Exception:
        logger.debug("Не удалось обновить сообщение истёкшего вызова", exc_info=True)


def schedule_challenge_expiry(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    chat_id: int,
    challenge_id: int,
    message_id: int,
    timeout_sec: float,
) -> None:
    job_queue = context.application.job_queue
    if not job_queue:
        logger.warning("JobQueue недоступен — таймер вызова не запланирован")
        return
    job_queue.run_once(
        expire_challenge_job,
        when=timeout_sec,
        data={
            "chat_id": chat_id,
            "challenge_id": challenge_id,
            "message_id": message_id,
        },
        name=f"challenge_{chat_id}_{challenge_id}",
    )
