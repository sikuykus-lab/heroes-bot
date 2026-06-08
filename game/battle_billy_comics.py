"""Билли Бутчер Comics (Secret V)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.battle_engine import set_ability_cooldown
if TYPE_CHECKING:
    from game.battle_engine import ActionResult, _ActionCtx
    from game.models import BattleState

DAMAGE_TABLE_BBC_LASER = {1: 10, 2: 15, 3: 20, 4: 25, 5: 30, 6: 35}
EXCUSE_CHARGE = {1: 25, 2: 25, 3: 25, 4: 25, 5: 35, 6: 35}


def apply_billy_comics_action(
    ctx: _ActionCtx,
    state: BattleState,
    actor_id: int,
    opp_id: int,
    extra_rolls: list[int],
    *,
    apply_damage,
    finish,
    opp_char: str,
) -> ActionResult | None:
    aid = ctx.action_id
    status = state.status_for(actor_id)
    opp_status = state.status_for(opp_id)

    if aid == "bbc_laser":
        dmg = DAMAGE_TABLE_BBC_LASER.get(ctx.roll, 10)
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "bbc_laser", 2)
        ctx.effect("Кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "bbc_crowbar":
        if ctx.roll <= 3:
            apply_damage(state, actor_id, opp_id, 15, ctx)
        else:
            apply_damage(state, actor_id, opp_id, 20, ctx)
            opp_status.miss_chance = max(opp_status.miss_chance, 0.8)
            ctx.effect("Сотрясение: 80% промах у врага на ход.")
        return finish(ctx, state)

    if aid == "bbc_excuse":
        if status.excuse_pct >= 100:
            status.excuse_pct = 0
            base = 12 if ctx.roll == 6 else 10
            mult = 4
            if extra_rolls:
                ctx.extra_rolls = list(extra_rolls)
                r2 = extra_rolls[0]
                mult = 6 if r2 >= 4 else 4
                ctx.effect(f"Второй кубик {r2}: урон ×{mult}")
            dmg = base * mult
            ctx.effect(f"Excuse Me Sir: {base}×{mult} = {dmg} HP!")
            apply_damage(state, actor_id, opp_id, dmg, ctx, ignore_dodge=True)
            res = finish(ctx, state)
            res.send_excuse_voice = True
            return res
        add = EXCUSE_CHARGE.get(ctx.roll, 25)
        status.excuse_pct = min(100, status.excuse_pct + add)
        ctx.effect(f"Excuse Me Sir: {status.excuse_pct}%")
        if status.excuse_pct >= 100:
            ctx.effect("Готово к выпуску!")
        from game.battle_engine import _switch_turn

        _switch_turn(state)
        from game.battle_engine import ActionResult

        return ActionResult(turn_report=ctx.to_report())

    if aid == "bbc_aura":
        status.excuse_pct = min(100, status.excuse_pct + 20)
        ctx.effect(f"Excuse Me Sir +20% (теперь {status.excuse_pct}%)")
        if ctx.roll == 6:
            status.absorb_pct = 100
            ctx.effect("Поглощение 100% на одну атаку!")
            apply_damage(state, actor_id, opp_id, 20, ctx)
            ctx.effect("Контратака монтировкой 20 HP!")
        else:
            status.absorb_pct = 90
            ctx.effect("Поглощение 90% на одну атаку противника.")
        set_ability_cooldown(status, "bbc_aura", 1)
        ctx.effect("Кулдаун 1 ход.")
        res = finish(ctx, state)
        res.send_aura_sticker = True
        res.send_aura_message = True
        return res

    return None
