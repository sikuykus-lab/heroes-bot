"""Ходы в бою."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from game import battle_engine, db
from game.currency import display_amount
from game.achievements import (
    announce_unlock,
    announce_unlocks,
    check_after_battle_rewards,
    on_beam_demote,
    on_v1_action_used,
    on_virus_used,
    on_virus_death,
)
from game.characters import action_disabled
from game.battle_mimic import mimic_effective_action_id
from game.media import AURA_FARMING_CAPTION, send_excuse_voice
from game.stickers import send_soldier_beam_sticker, send_soldier_beam_sticker_index
from game import rewards as rewards_logic
from game.keyboards import battle_keyboard
from game.models import BattleState
from game.turn_report import TurnReport
from handlers.battle_messages import (
    cleanup_battle_messages,
    delete_message_safe,
    replace_battle_message,
    roll_battle_dice,
)
from handlers.battle_ui import format_battle_end, format_battle_message
from handlers.utils import display_name


def _demote_to_loh(chat_id: int, user_id: int) -> None:
    p = db.get_or_create_player(chat_id, user_id)
    p.v_tier = "none"
    p.active_character = "loh"
    p.v24_battles_left = 0
    db.save_player(p)


def _virus_victim_aftermath(chat_id: int, user_id: int) -> None:
    _demote_to_loh(chat_id, user_id)


def _finish_battle_rewards(
    chat_id: int,
    state: BattleState,
    winner_id: int,
    loser_id: int,
) -> tuple[int, int, list]:
    winner = db.get_or_create_player(chat_id, winner_id)
    loser = db.get_or_create_player(chat_id, loser_id)
    win_coins, loss_coins = rewards_logic.apply_battle_rewards(
        chat_id, winner_id, loser_id, winner, loser
    )
    unlocks = check_after_battle_rewards(
        chat_id, state, winner_id, winner, loser
    )
    return win_coins, loss_coins, unlocks


async def _publish_battle_turn(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    state: BattleState,
    p1,
    p2,
) -> None:
    turn_player = p1 if state.turn_user_id == p1.user_id else p2
    text = format_battle_message(state, p1, p2)
    kb = battle_keyboard(state, state.turn_user_id, turn_player)
    await replace_battle_message(
        context.bot, chat_id, state, text, reply_markup=kb
    )


async def _finish_battle(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    state: BattleState,
    p1,
    p2,
    result: battle_engine.ActionResult,
    footer: str,
) -> None:
    await cleanup_battle_messages(context.bot, chat_id, state)
    if result.turn_report:
        state.last_turn_report = result.turn_report.to_dict()

    text = format_battle_end(state, p1, p2, footer)
    await replace_battle_message(context.bot, chat_id, state, text)
    db.delete_battle_by_id(state.battle_id)


async def _auto_skip_stun(state: BattleState) -> TurnReport | None:
    """Пропуск хода из-за оглушения — показываем в следующем сообщении."""
    for _ in range(4):
        uid = state.turn_user_id
        status = state.status_for(uid)
        msg = battle_engine.consume_stun_skip(status)
        if not msg:
            break
        state.turn_user_id = state.opponent_id(uid)
        battle_engine.begin_turn(state)
        return TurnReport(roll=0, action_label="Оглушение", effect_lines=[msg])
    return None


async def on_battle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return

    parts = query.data.split(":")
    if len(parts) < 3:
        return
    try:
        battle_id = int(parts[1])
    except ValueError:
        return
    action_id = parts[2]

    chat = query.message.chat if query.message else None
    if not chat:
        return
    chat_id = chat.id
    user_id = query.from_user.id

    active = db.get_battle_by_id(battle_id)
    if not active:
        await query.answer("Бой не найден.", show_alert=True)
        return
    bid, chat_id, p1_id, p2_id, state = active
    if bid != battle_id:
        await query.answer("Устаревшее сообщение боя.", show_alert=True)
        return

    if user_id not in (p1_id, p2_id):
        await query.answer("Вы не в этом бою.", show_alert=True)
        return

    p1 = db.get_or_create_player(chat_id, p1_id)
    p2 = db.get_or_create_player(chat_id, p2_id)
    actor = p1 if user_id == p1_id else p2

    if action_id == "surrender":
        await query.answer()
        opp_id = state.opponent_id(user_id)
        report = TurnReport(roll=0, action_label="Сдача", effect_lines=["Сдался."])
        state.last_turn_report = report.to_dict()
        result = battle_engine.ActionResult(
            turn_report=report,
            ended=True,
            winner_id=opp_id,
            loser_id=user_id,
        )
        await _finish_battle(
            context,
            chat_id,
            state,
            p1,
            p2,
            result,
            f"{actor.display_name} сдался.",
        )
        return

    if state.beam_response_user_id is not None:
        if user_id != state.beam_response_user_id:
            await query.answer("Сейчас жертва луча выбирает реакцию.", show_alert=True)
            return
        if action_id not in ("beam_dodge", "beam_counter"):
            await query.answer("Выбери уворот или контратаку.", show_alert=True)
            return
    elif state.turn_user_id != user_id:
        await query.answer("Сейчас не ваш ход.", show_alert=True)
        return

    if action_id == "item_virus":
        if actor.virus_count <= 0:
            await query.answer("Нет вируса.", show_alert=True)
            return
        actor.virus_count -= 1
        db.save_player(actor)

    if action_id not in ("beam_dodge", "beam_counter", "surrender"):
        character = (
            state.p1_character if user_id == state.p1_id else state.p2_character
        )
        status = state.status_for(user_id)
        if action_disabled(action_id, status, character):
            await query.answer(
                "Способность недоступна — ход не засчитан.",
                show_alert=True,
            )
            return

    await query.answer()

    if action_id == "item_virus":
        ach = on_virus_used(chat_id, user_id)
        if ach:
            await announce_unlock(context.bot, chat_id, user_id, ach)
    elif action_id not in ("surrender", "battle_escape") and actor.v_tier == "v1":
        ach = on_v1_action_used(chat_id, user_id)
        if ach:
            await announce_unlock(context.bot, chat_id, user_id, ach)

    roll = await roll_battle_dice(context.bot, chat_id, state, user_id=user_id)

    if action_id in ("beam_dodge", "beam_counter"):
        result = battle_engine.apply_beam_response(state, user_id, action_id, roll)
        battle_engine.touch_battle_activity(state)
    else:
        extra_rolls: list[int] = []
        character = (
            state.p1_character if user_id == state.p1_id else state.p2_character
        )
        actor_st = state.status_for(user_id)
        effective_id = mimic_effective_action_id(
            action_id, actor_st, character
        )
        if action_id == "mm_random" and roll == 4:
            extra_rolls.append(
                await roll_battle_dice(context.bot, chat_id, state, user_id=user_id)
            )
        elif effective_id == "at_rapid":
            extra_rolls.append(
                await roll_battle_dice(context.bot, chat_id, state, user_id=user_id)
            )
        elif effective_id == "sl_charges":
            extra_rolls.append(
                await roll_battle_dice(context.bot, chat_id, state, user_id=user_id)
            )
        elif effective_id in ("bu_barrage", "bn_knife"):
            extra_rolls.append(
                await roll_battle_dice(context.bot, chat_id, state, user_id=user_id)
            )
        elif effective_id == "tp_heavy" and roll == 6:
            extra_rolls.append(
                await roll_battle_dice(context.bot, chat_id, state, user_id=user_id)
            )
        elif effective_id == "bbc_excuse":
            if actor_st.excuse_pct >= 100:
                extra_rolls.append(
                    await roll_battle_dice(context.bot, chat_id, state, user_id=user_id)
                )

        opp = p2 if user_id == p1_id else p1
        result = battle_engine.apply_action(
            state,
            user_id,
            action_id,
            roll,
            actor_v_tier=actor.v_tier,
            opponent_v_tier=opp.v_tier,
            extra_rolls=extra_rolls,
        )

    if result.turn_report:
        state.last_turn_report = result.turn_report.to_dict()
    if result.demote_to_loh_user_id:
        ach = on_beam_demote(chat_id, result.demote_to_loh_user_id)
        if ach:
            await announce_unlock(
                context.bot, chat_id, result.demote_to_loh_user_id, ach
            )
        _demote_to_loh(chat_id, result.demote_to_loh_user_id)
    if result.virus_victim_id:
        ach = on_virus_death(chat_id, result.virus_victim_id)
        if ach:
            await announce_unlock(
                context.bot, chat_id, result.virus_victim_id, ach
            )
        _virus_victim_aftermath(chat_id, result.virus_victim_id)

    if result.send_soldier_beam_sticker:
        await send_soldier_beam_sticker(
            context.bot, chat_id, context.application.bot_data
        )
    if result.send_aura_sticker:
        await send_soldier_beam_sticker_index(
            context.bot, chat_id, context.application.bot_data, 1
        )
    if result.send_aura_message:
        await context.bot.send_message(chat_id=chat_id, text=AURA_FARMING_CAPTION)
    if result.send_excuse_voice:
        await send_excuse_voice(context.bot, chat_id)

    await delete_message_safe(context.bot, chat_id, state.last_dice_message_id)
    state.last_dice_message_id = None

    if result.ended or result.escaped_user_id:
        footer = "Бой завершён: побег." if result.escaped_user_id else ""
        if result.ended and result.winner_id:
            win_coins, loss_coins, unlocks = _finish_battle_rewards(
                chat_id, state, result.winner_id, result.loser_id
            )
            await announce_unlocks(
                context.bot, chat_id, result.winner_id, unlocks
            )
            rewards_logic.decrement_v24_after_battle(
                db.get_or_create_player(chat_id, state.p1_id)
            )
            rewards_logic.decrement_v24_after_battle(
                db.get_or_create_player(chat_id, state.p2_id)
            )
            wname = (
                db.get_or_create_player(chat_id, result.winner_id).display_name
                or "Победитель"
            )
            cur = db.get_chat_currency(chat_id)
            footer = (
                f"🏆 {wname} победил!\n"
                f"+{display_amount(cur, win_coins)} / +{display_amount(cur, loss_coins)}."
            )
        await _finish_battle(context, chat_id, state, p1, p2, result, footer)
        return

    stun_report = await _auto_skip_stun(state)
    if stun_report:
        state.last_turn_report = stun_report.to_dict()

    win = battle_engine._check_win(state)
    if win and win.ended:
        win_coins, loss_coins, unlocks = _finish_battle_rewards(
            chat_id, state, win.winner_id, win.loser_id
        )
        await announce_unlocks(context.bot, chat_id, win.winner_id, unlocks)
        wname = winner.display_name or "Победитель"
        await _finish_battle(
            context,
            chat_id,
            state,
            p1,
            p2,
            win,
            (
                f"🏆 {wname} победил!\n"
                f"+{display_amount(db.get_chat_currency(chat_id), win_coins)} / "
                f"+{display_amount(db.get_chat_currency(chat_id), loss_coins)}."
            ),
        )
        return

    battle_engine.touch_battle_activity(state)
    db.save_battle(bid, chat_id, p1_id, p2_id, state)
    p1 = db.get_or_create_player(chat_id, p1_id)
    p2 = db.get_or_create_player(chat_id, p2_id)
    await _publish_battle_turn(context, chat_id, state, p1, p2)
    battle_engine.touch_battle_activity(state)
    db.save_battle(bid, chat_id, p1_id, p2_id, state)
