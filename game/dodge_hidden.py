"""Скрытый исход уворотов до хода противника."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from game.battle_engine import _ActionCtx
    from game.models import BattleState, PlayerBattleStatus

DODGE_HIDDEN_PUBLIC = "Уворот — результат скрыт до хода противника."


def register_hidden_dodge(
    status: PlayerBattleStatus,
    reveal_lines: list[str],
    *,
    dodge_active: bool = False,
    absorb_pct: int | None = None,
) -> None:
    status.dodge_hidden_pending = True
    status.dodge_hidden_lines = list(reveal_lines)
    status.dodge_active = dodge_active
    if absorb_pct is not None:
        status.absorb_pct = absorb_pct


def mark_dodge_turn_hidden(ctx: _ActionCtx) -> None:
    ctx.effect(DODGE_HIDDEN_PUBLIC)
    ctx.dodge_outcome_hidden = True


def reveal_hidden_dodge(status: PlayerBattleStatus, ctx: _ActionCtx) -> bool:
    if not status.dodge_hidden_pending:
        return False
    for line in status.dodge_hidden_lines:
        ctx.effect(line)
    status.dodge_hidden_pending = False
    status.dodge_hidden_lines = []
    return True


def reveal_dodger_before_opponent_turn(
    state: BattleState, opponent_actor_id: int, ctx: _ActionCtx
) -> None:
    """Показать исход уворота соперника в конце хода атакующего."""
    dodger_id = state.opponent_id(opponent_actor_id)
    reveal_hidden_dodge(state.status_for(dodger_id), ctx)
