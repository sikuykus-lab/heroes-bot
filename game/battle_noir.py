"""Чёрный Нуар и Летающий Нуар."""

from __future__ import annotations

from typing import TYPE_CHECKING

from game.battle_engine import set_ability_cooldown
from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

if TYPE_CHECKING:
    from game.battle_engine import ActionResult, _ActionCtx
    from game.models import BattleState

DAMAGE_BN_MIGHTY = {1: 11, 2: 15, 3: 18, 4: 20, 5: 25, 6: 30}
DAMAGE_FN_PUNCH = {1: 7, 2: 9, 3: 11, 4: 15, 5: 20, 6: 25}


def apply_noir_action(
    ctx: _ActionCtx,
    state: BattleState,
    actor_id: int,
    opp_id: int,
    extra_rolls: list[int],
    *,
    apply_damage,
    finish,
    switch_turn,
) -> ActionResult | None:
    aid = ctx.action_id
    status = state.status_for(actor_id)
    opp_status = state.status_for(opp_id)

    if aid == "bn_mighty":
        dmg = DAMAGE_BN_MIGHTY.get(ctx.roll, 11)
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "bn_mighty", 2)
        ctx.effect("Отдышка: кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "bn_knife":
        base = 3 if ctx.roll <= 3 else (5 if ctx.roll <= 5 else 6)
        r2 = (extra_rolls or [1])[0]
        ctx.extra_rolls = [r2]
        mult = 2 if r2 <= 3 else (3 if r2 <= 5 else 4)
        dmg = base * mult
        ctx.effect(f"Бросок ножа: {base}×{mult} = {dmg} HP!")
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        return finish(ctx, state)

    if aid == "bn_regen_dodge":
        r = ctx.roll
        if r <= 3:
            hp = state.hp_for(actor_id)
            state.set_hp_for(actor_id, min(100, hp + 5))
            register_hidden_dodge(status, ["Регенеративный уворот: неудача, +5 HP."])
        elif r <= 5:
            hp = state.hp_for(actor_id)
            state.set_hp_for(actor_id, min(100, hp + 5))
            register_hidden_dodge(
                status,
                ["Регенеративный уворот: удачно, +5 HP!"],
                dodge_active=True,
            )
        else:
            hp = state.hp_for(actor_id)
            state.set_hp_for(actor_id, min(100, hp + 3))
            register_hidden_dodge(
                status,
                ["Регенеративный уворот: удачно, контратака 5 HP, +3 HP!"],
                dodge_active=True,
            )
            apply_damage(state, actor_id, opp_id, 5, ctx)
        mark_dodge_turn_hidden(ctx)
        return finish(ctx, state)

    if aid == "bn_friends":
        r = ctx.roll
        if r <= 3:
            status.damage_dealt_mult = 1.1
            status.dealt_mult_turns = 1
            ctx.effect("Ради друзей: +10% урона на 1 ход!")
        elif r <= 5:
            status.damage_dealt_mult = 1.15
            status.dealt_mult_turns = 1
            ctx.effect("Ради друзей: +15% урона на 1 ход!")
        else:
            status.damage_dealt_mult = 1.3
            status.dealt_mult_turns = 2
            ctx.effect("Ради друзей: +30% урона на 2 хода!")
            ctx.effect("Он в бешенстве.")
        set_ability_cooldown(status, "bn_friends", 2)
        ctx.effect("Кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "bn_stolen_shot":
        if status.noir_stolen_used:
            ctx.effect("Украденный выстрел уже использован в этом бою.")
            return finish(ctx, state)
        status.noir_stolen_used = True
        hit = ctx.roll >= 4
        ctx.effect(
            "Нуар воспользовался украденным пистолетом пороха с последним патроном "
            f"и в итоге {'попал' if hit else 'не попал'}."
        )
        if hit:
            apply_damage(state, actor_id, opp_id, 20, ctx)
            opp_status.stunned = 1
            ctx.effect("Оглушение: противник пропускает ход!")
        return finish(ctx, state)

    if aid == "fn_punch":
        dmg = DAMAGE_FN_PUNCH.get(ctx.roll, 7)
        if status.noir_punch_buff_turns > 0:
            dmg = int(dmg * status.noir_punch_buff)
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        return finish(ctx, state)

    if aid == "fn_katana":
        if ctx.roll <= 4:
            dmg = 15
        else:
            dmg = 20
            opp_status.aim_impaired_turns = 2
            opp_status.aim_impaired_miss = 0.3
            ctx.effect("Раненая конечность: 30% промах противнику на 2 хода!")
        apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "fn_katana", 2)
        ctx.effect("Кулдаун 2 хода.")
        return finish(ctx, state)

    if aid == "fn_actor":
        if ctx.roll <= 3:
            status.noir_punch_buff = 1.15
            status.noir_punch_buff_turns = 1
            ctx.effect("Хороший актёр: +15% к усиленным ударам на 1 ход!")
        else:
            status.noir_punch_buff = 1.25
            status.noir_punch_buff_turns = 1
            status.noir_actor_dodge = True
            ctx.effect("Хороший актёр: +25% к ударам и уклонение от следующей атаки!")
        return finish(ctx, state)

    if aid == "fn_bulletproof":
        if status.fn_bp_used:
            ctx.effect("Пуленепробиваемый уже использован в этом бою.")
            return finish(ctx, state)
        status.fn_bp_used = True
        status.noir_bulletproof_turns = 4
        status.damage_taken_mult = 1.15
        status.taken_mult_turns = 4
        ctx.effect(
            "Пуленепробиваемый: неуязвимость к урону (кроме ударов и зарядок) на 4 хода!"
        )
        ctx.effect("Уязвимость: +15% получаемого урона на 4 хода.")
        return finish(ctx, state)

    return None
