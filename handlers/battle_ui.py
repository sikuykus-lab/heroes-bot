"""Отрисовка сообщения боя."""

from __future__ import annotations

import html

from game.characters import player_status_label
from game.models import BattleState, Player
from game.turn_report import TurnReport


def _rank(player: Player, battle_character: str) -> str:
    return player_status_label(player.v_tier, battle_character)


def _player_line(player: Player, battle_character: str, hp: int) -> str:
    name = html.escape(player.display_name or "Игрок")
    rank = html.escape(_rank(player, battle_character))
    return f"{name} [{rank}] — {hp} HP"


def _turn_line(player: Player) -> str:
    name = html.escape(player.display_name or "Игрок")
    return f'Ход: <a href="tg://user?id={player.user_id}">{name}</a>'


def _format_last_turn(
    report: TurnReport,
    state: BattleState,
    p1: Player,
    p2: Player,
) -> list[str]:
    lines: list[str] = [""]
    if report.dodge_outcome_hidden:
        if report.action_label:
            lines.append(html.escape(report.action_label))
        lines.append(html.escape("🎲 Исход уворота скрыт до хода противника"))
    elif report.roll > 0:
        lines.append(f"🎲 Выпало: {report.roll}")
    for i, er in enumerate(report.extra_rolls, start=2):
        lines.append(f"🎲 Кубик {i}: {er}")
    if report.action_label and not report.dodge_outcome_hidden:
        lines.append(html.escape(report.action_label))
    for raw in report.effect_lines:
        if raw.startswith("🎲"):
            continue
        lines.append(html.escape(raw))
    if (
        report.damage
        and report.damage_target_id is not None
        and not report.dodge_outcome_hidden
    ):
        target = p1 if report.damage_target_id == p1.user_id else p2
        tname = html.escape(target.display_name or "Игрок")
        hp = state.hp_for(report.damage_target_id)
        lines.append(
            f"Урон: - {report.damage} хп 💔 (Здоровье {tname}: {hp} ❤️)"
        )
    return lines


def format_battle_message(
    state: BattleState,
    p1: Player,
    p2: Player,
) -> str:
    """Первичное сообщение — без блока прошлого хода; иначе — только последний ход."""
    turn_player = p1 if state.turn_user_id == p1.user_id else p2
    lines = [
        "⚔️ Бой",
        _player_line(p1, state.p1_character, state.p1_hp),
        _player_line(p2, state.p2_character, state.p2_hp),
        "",
        _turn_line(turn_player),
    ]
    if state.beam_response_user_id == turn_player.user_id:
        lines.append("☢️ Луч Солдатика — предударный ход (урон ещё не нанесён)!")
    report = TurnReport.from_dict(state.last_turn_report)
    if report:
        lines.extend(_format_last_turn(report, state, p1, p2))
    return "\n".join(lines)


def format_battle_end(
    state: BattleState,
    p1: Player,
    p2: Player,
    footer: str,
) -> str:
    base = format_battle_message(state, p1, p2)
    return base + "\n\n" + html.escape(footer)
