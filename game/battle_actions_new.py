"""Способности новых персонажей (Бутчеры, А-Трейн, Ньюман, Телепорт)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from game.characters import (
    DAMAGE_TABLE_AT_RAPID_HIT,
    DAMAGE_TABLE_AT_RUSH,
    DAMAGE_TABLE_NM_INTERNAL,
    DAMAGE_TABLE_PUNCH_H,
    DAMAGE_TABLE_STANDARD,
    DAMAGE_TABLE_WB_LASER,
    NEWMAN_TEAR_CHARGE,
)

from game.battle_engine import set_ability_cooldown
from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

if TYPE_CHECKING:
    from game.battle_engine import ActionResult, _ActionCtx
    from game.models import BattleState


def apply_new_character_action(
    ctx: _ActionCtx,
    state: BattleState,
    actor_id: int,
    opp_id: int,
    extra_rolls: list[int],
    *,
    apply_damage,
    finish,
    check_win,
    switch_turn,
) -> ActionResult | None:
    """Возвращает ActionResult если действие обработано, иначе None."""
    aid = ctx.action_id
    status = state.status_for(actor_id)
    opp_status = state.status_for(opp_id)

    if aid in ("wb_punch", "bb_punch"):
        dmg = DAMAGE_TABLE_STANDARD.get(ctx.roll, 7)
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        return finish(ctx, state)

    if aid in ("at_punch", "nm_punch", "tp_punch"):
        dmg = DAMAGE_TABLE_PUNCH_H.get(ctx.roll, 5)
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        return finish(ctx, state)

    if aid == "wb_laser":
        dmg = DAMAGE_TABLE_WB_LASER.get(ctx.roll, 5)
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "wb_laser", 1)
        ctx.effect("Лазерные глаза: кулдаун 1 ход.")
        return finish(ctx, state)

    if aid == "wb_dash_dodge":
        if ctx.roll % 2 == 0:
            register_hidden_dodge(
                status, ["Рывковый уворот: увернулся!"], dodge_active=True
            )
        else:
            register_hidden_dodge(status, ["Рывковый уворот: не увернулся."])
        mark_dodge_turn_hidden(ctx)
        return finish(ctx, state)

    if aid == "wb_barrage":
        if ctx.roll <= 4:
            dmg = 20
        elif ctx.roll == 5:
            dmg = 30
        else:
            dmg = 40
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "wb_barrage", 3)
        ctx.effect("Шквал ударов: кулдаун 3 хода.")
        return finish(ctx, state)

    if aid == "bb_tentacle":
        if ctx.roll <= 4:
            dmg = 15
        else:
            dmg = 20
            opp_status.stunned = 1
            ctx.effect("Оглушение на 1 ход!")
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "bb_tentacle", 2)
        ctx.effect("Удушение щупальцами: кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "bb_sensual_dodge":
        if ctx.roll in (2, 4, 6):
            lines = ["Чувственный уворот: увернулся!"]
            if ctx.roll == 6:
                apply_damage(state, actor_id, opp_id, 10, ctx)
                lines.append("Контрудар: 10 HP!")
            register_hidden_dodge(status, lines, dodge_active=True)
        else:
            apply_damage(state, actor_id, actor_id, 5, ctx, ignore_dodge=True)
            register_hidden_dodge(status, ["Чувственный уворот: не увернулся."])
        mark_dodge_turn_hidden(ctx)
        return finish(ctx, state)

    if aid == "bb_crowbar":
        if ctx.roll % 2 == 1:
            dmg = 10
        else:
            dmg = 15
            opp_status.miss_chance = max(opp_status.miss_chance, 0.5)
            ctx.effect("Сотрясение: 50% промах у врага на ход.")
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "bb_crowbar", 1)
        ctx.effect("Монтировка: кулдаун 1 ход.")
        return finish(ctx, state)

    if aid == "at_rush":
        dmg = DAMAGE_TABLE_AT_RUSH.get(ctx.roll, 7)
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "at_rush", 2)
        ctx.effect("Скоростной напор: кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "at_rapid":
        dmg_roll = ctx.roll
        hits_roll = extra_rolls[0] if extra_rolls else dmg_roll
        ctx.extra_rolls = [hits_roll]
        per_hit = DAMAGE_TABLE_AT_RAPID_HIT.get(dmg_roll, 3)
        hits = max(1, min(6, hits_roll))
        total = 0
        for _ in range(hits):
            total += per_hit
        apply_damage(state, actor_id, opp_id, total, ctx)
        ctx.effect(f"Быстрые удары: {hits}×{per_hit} = {total} HP")
        return finish(ctx, state)

    if aid == "at_dodge":
        if ctx.roll % 2 == 0:
            register_hidden_dodge(
                status, ["Скоростной уворот: увернулся!"], dodge_active=True
            )
        else:
            apply_damage(state, actor_id, actor_id, 5, ctx, ignore_dodge=True)
            register_hidden_dodge(
                status,
                ["Задели: поглощение 30% на этот ход."],
                absorb_pct=30,
            )
        mark_dodge_turn_hidden(ctx)
        return finish(ctx, state)

    if aid == "at_accel":
        bonus = 20 if ctx.roll % 2 == 0 else 10
        status.damage_dealt_mult = 1.0 + bonus / 100
        status.dealt_mult_turns = 2
        set_ability_cooldown(status, "at_accel", 3)
        ctx.effect(f"Ускорение: +{bonus}% урона на 2 хода. Кулдаун 3.")
        return finish(ctx, state)

    if aid == "nm_internal":
        dmg = DAMAGE_TABLE_NM_INTERNAL.get(ctx.roll, 10)
        if ctx.roll == 6:
            opp_status.stunned = 1
            ctx.effect("Внутренний удар: оглушение!")
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "nm_internal", 2)
        ctx.effect("Кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "nm_tear":
        add = NEWMAN_TEAR_CHARGE.get(ctx.roll, 15)
        status.newman_tear_pct = min(100, status.newman_tear_pct + add)
        ctx.effect(f"Разрыв: +{add}% (всего {status.newman_tear_pct}%)")
        return finish(ctx, state)

    if aid == "nm_head_explode":
        if status.newman_tear_pct < 100:
            ctx.effect("Нужно 100% накопления разрыва.")
            return finish(ctx, state)
        if ctx.roll == 6:
            dmg = 100
            ctx.effect("ВЗРЫВ ГОЛОВЫ!")
        else:
            dmg = 40
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        status.newman_tear_pct = 0
        return finish(ctx, state)

    if aid == "nm_regen_dodge":
        if ctx.roll in (2, 4, 6):
            lines = ["Регенеративный уворот!"]
            if ctx.roll == 6:
                hp = state.hp_for(actor_id)
                state.set_hp_for(actor_id, min(100, hp + 10))
                lines.append("+10 HP")
            register_hidden_dodge(status, lines, dodge_active=True)
        else:
            apply_damage(state, actor_id, actor_id, 5, ctx, ignore_dodge=True)
            register_hidden_dodge(status, ["Не увернулся."])
        mark_dodge_turn_hidden(ctx)
        return finish(ctx, state)

    if aid == "nm_limb_weak":
        if ctx.roll <= 4:
            mult = 0.9
            ctx.effect("Враг: −10% урона на ход.")
        elif ctx.roll == 5:
            mult = 0.8
            ctx.effect("Враг: −20% урона на ход.")
        else:
            mult = 0.7
            ctx.effect("Враг: −30% урона на ход.")
        opp_status.damage_dealt_mult = mult
        opp_status.dealt_mult_turns = 1
        set_ability_cooldown(status, "nm_limb_weak", 2)
        ctx.effect("Кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "tp_barrage":
        if ctx.roll <= 4:
            dmg = 15
        else:
            dmg = 20
            opp_status.miss_chance = max(opp_status.miss_chance, 0.3)
            ctx.effect("30% промах у врага на ход.")
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "tp_barrage", 2)
        ctx.effect("Кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "tp_dodge":
        r = ctx.roll
        if r in (1, 3):
            apply_damage(state, actor_id, actor_id, 5, ctx, ignore_dodge=True)
            register_hidden_dodge(status, ["Телепорт-уворот: неудача."])
        elif r == 2:
            register_hidden_dodge(
                status, ["Телепорт-уворот: увернулся!"], dodge_active=True
            )
        elif r == 4:
            apply_damage(state, actor_id, opp_id, 5, ctx)
            register_hidden_dodge(
                status,
                ["Телепорт-уворот: увернулся, контрудар 5 HP!"],
                dodge_active=True,
            )
        elif r == 5:
            apply_damage(state, actor_id, opp_id, 10, ctx)
            register_hidden_dodge(
                status, ["Телепорт-уворот: неудача, контрудар 10 HP!"]
            )
        else:
            apply_damage(state, actor_id, opp_id, 10, ctx)
            register_hidden_dodge(
                status,
                ["Телепорт-уворот: увернулся, контрудар 10 HP!"],
                dodge_active=True,
            )
        mark_dodge_turn_hidden(ctx)
        return finish(ctx, state)

    if aid == "tp_heavy":
        if ctx.roll <= 5:
            dmg = 15
            opp_status.damage_taken_mult = 1.15
            opp_status.taken_mult_turns = 1
            ctx.effect("Противник: +15% получаемого урона на ход.")
            apply_damage(state, actor_id, opp_id, dmg, ctx)
        else:
            dmg = 20
            ctx.effect("Тяжёлый удар: 20 HP!")
            if extra_rolls:
                ctx.extra_rolls = list(extra_rolls)
                r2 = extra_rolls[0]
                if r2 <= 4:
                    status.damage_taken_mult = 1.2
                    status.taken_mult_turns = 1
                    ctx.effect(f"Второй кубик {r2}: +20% урона от врага на ход.")
                else:
                    ctx.effect(f"Второй кубик {r2}: без уязвимости.")
            apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "tp_heavy", 2)
        ctx.effect("Кулдаун 2 хода.")
        return finish(ctx, state)

    return None
