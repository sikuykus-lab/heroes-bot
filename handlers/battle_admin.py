"""Админская отмена боёв и проверка бездействия."""

from __future__ import annotations

import logging
import time

from telegram.ext import ContextTypes

from game import db
from game.config import BATTLE_INACTIVITY_SEC
from game.turn_report import TurnReport
from handlers.callbacks_battle import _finish_battle
from game import battle_engine

logger = logging.getLogger(__name__)


async def force_cancel_battle(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    battle_id: int,
    p1_id: int,
    p2_id: int,
    state,
    *,
    reason: str,
) -> None:
    p1 = db.get_or_create_player(chat_id, p1_id)
    p2 = db.get_or_create_player(chat_id, p2_id)
    report = TurnReport(
        roll=0, action_label="Отмена", effect_lines=[reason]
    )
    result = battle_engine.ActionResult(turn_report=report)
    state.last_turn_report = report.to_dict()
    await _finish_battle(context, chat_id, state, p1, p2, result, reason)


async def check_stale_battles_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    now = time.time()
    for battle_id, chat_id, p1_id, p2_id, state in db.list_all_active_battles():
        last = state.last_activity_at or 0
        if last <= 0:
            state.last_activity_at = now
            db.save_battle(battle_id, chat_id, p1_id, p2_id, state)
            continue
        if now - last < BATTLE_INACTIVITY_SEC:
            continue
        try:
            await force_cancel_battle(
                context,
                chat_id,
                battle_id,
                p1_id,
                p2_id,
                state,
                reason="Бой отменён: нет ходов более 5 минут.",
            )
        except Exception:
            logger.exception("Не удалось отменить бой #%s", battle_id)


def schedule_battle_inactivity_checks(app) -> None:
    job_queue = app.job_queue
    if not job_queue:
        logger.warning("JobQueue недоступен — автоотмена боёв не запланирована")
        return
    job_queue.run_repeating(
        check_stale_battles_job,
        interval=60,
        first=60,
        name="battle_inactivity",
    )
