"""Логика боя и применение способностей."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field

from game.characters import (
    BEAM_CHARGE,
    BUTCHER_RUSH_CHARGE,
    CHARACTER_NAMES,
    SCORCHED_CHARGE,
    get_actions_for_character,
    DAMAGE_TABLE_LASER,
    DAMAGE_TABLE_SB_BULLET,
    DAMAGE_TABLE_SF_LIGHTNING,
    DAMAGE_TABLE_STANDARD,
    DAMAGE_TABLE_STAR_PUNCH,
    DAMAGE_TABLE_STRIKE_S,
    STAR_HEAVY_CHARGE,
    STORM_CHARGE,
    action_disabled,
    get_action_label,
    is_super_tier,
)
from game.battle_damage_rules import bypasses_bulletproof
from game.dodge_hidden import reveal_dodger_before_opponent_turn, reveal_hidden_dodge
from game.models import BattleState, PlayerBattleStatus
from game.turn_report import TurnReport


@dataclass
class ActionResult:
    turn_report: TurnReport | None = None
    ended: bool = False
    winner_id: int | None = None
    loser_id: int | None = None
    escaped_user_id: int | None = None
    demote_to_loh_user_id: int | None = None
    virus_victim_id: int | None = None
    send_soldier_beam_sticker: bool = False
    send_aura_sticker: bool = False
    send_aura_message: bool = False
    send_excuse_voice: bool = False

    @property
    def lines(self) -> list[str]:
        """Для совместимости (финиш боя)."""
        if not self.turn_report:
            return []
        out = [f"🎲 Выпало: {self.turn_report.roll}"]
        out.extend(self.turn_report.effect_lines)
        return out


@dataclass
class _ActionCtx:
    roll: int
    action_id: str
    actor_id: int
    effect_lines: list[str] = field(default_factory=list)
    damage: int | None = None
    damage_target_id: int | None = None
    extra_rolls: list[int] = field(default_factory=list)
    dodge_outcome_hidden: bool = False

    def effect(self, text: str) -> None:
        self.effect_lines.append(text)

    def to_report(self) -> TurnReport:
        return TurnReport(
            roll=self.roll,
            action_label=get_action_label(self.action_id),
            effect_lines=list(self.effect_lines),
            damage=self.damage,
            damage_target_id=self.damage_target_id,
            extra_rolls=list(self.extra_rolls),
            dodge_outcome_hidden=self.dodge_outcome_hidden,
        )


def set_ability_cooldown(status: PlayerBattleStatus, action_id: str, own_turns: int) -> None:
    """Кулдаун на N собственных ходов (ходы соперника не считаются)."""
    if own_turns <= 0:
        return
    # +1: первый тик в начале следующего своего хода оставляет способность заблокированной
    status.cooldowns[action_id] = own_turns + 1


def _tick_cooldowns(status: PlayerBattleStatus) -> None:
    for key in list(status.cooldowns):
        if status.cooldowns[key] > 0:
            status.cooldowns[key] -= 1
            if status.cooldowns[key] <= 0:
                del status.cooldowns[key]


def _tick_status_turn_start(status: PlayerBattleStatus) -> list[str]:
    _tick_cooldowns(status)
    if status.dealt_mult_turns > 0:
        status.dealt_mult_turns -= 1
        if status.dealt_mult_turns <= 0:
            status.damage_dealt_mult = 1.0
    if status.taken_mult_turns > 0:
        status.taken_mult_turns -= 1
        if status.taken_mult_turns <= 0:
            status.damage_taken_mult = 1.0
    if status.dodge_forbidden_turns > 0:
        status.dodge_forbidden_turns -= 1
    if status.ability_block_turns > 0:
        status.ability_block_turns -= 1
        if status.ability_block_turns <= 0:
            status.anti_v_disabled = []
    if status.noir_bulletproof_turns > 0:
        status.noir_bulletproof_turns -= 1
    if status.noir_punch_buff_turns > 0:
        status.noir_punch_buff_turns -= 1
        if status.noir_punch_buff_turns <= 0:
            status.noir_punch_buff = 1.0
    if status.aim_impaired_turns > 0:
        status.aim_impaired_turns -= 1
        if status.aim_impaired_turns <= 0:
            status.aim_impaired_miss = 0.0
    if status.absorb_pct > 0 and status.cooldowns.get("_absorb_turns", 0) <= 0:
        status.absorb_pct = 0
    return []


def _tick_status_turn_end(status: PlayerBattleStatus) -> None:
    if status.blind_turns > 0:
        status.blind_turns -= 1


def touch_battle_activity(state: BattleState) -> None:
    state.last_activity_at = time.time()


def consume_stun_skip(status: PlayerBattleStatus) -> str | None:
    if status.stunned > 0:
        status.stunned -= 1
        return "Оглушён — пропуск хода."
    return None


def _apply_damage(
    state: BattleState,
    attacker_id: int,
    defender_id: int,
    base_damage: int,
    ctx: _ActionCtx,
    *,
    ignore_dodge: bool = False,
) -> int:
    def_status = state.status_for(defender_id)

    if def_status.noir_actor_dodge and defender_id != attacker_id:
        def_status.noir_actor_dodge = False
        ctx.effect("Хороший актёр: атака уклонена!")
        return 0

    if (
        def_status.noir_bulletproof_turns > 0
        and defender_id != attacker_id
    ):
        atk_status = state.status_for(attacker_id)
        if not bypasses_bulletproof(ctx.action_id, atk_status):
            ctx.effect("Пуленепробиваемый: урон заблокирован!")
            return 0

    if not ignore_dodge and def_status.dodge_active:
        reveal_hidden_dodge(def_status, ctx)
        def_status.dodge_active = False
        ctx.effect("Атака заблокирована уворотом!")
        return 0

    atk_status = state.status_for(attacker_id)
    miss_chance = atk_status.miss_chance
    if atk_status.aim_impaired_turns > 0:
        miss_chance = max(miss_chance, atk_status.aim_impaired_miss)
    if atk_status.blind_turns > 0:
        miss_chance = max(miss_chance, 0.5)

    if miss_chance > 0 and random.random() < miss_chance:
        ctx.effect("Промах (ослепление)!")
        atk_status.miss_chance = 0.0
        return 0

    atk_status.miss_chance = 0.0

    damage = base_damage
    def_status = state.status_for(defender_id)
    damage = int(damage * atk_status.damage_dealt_mult)
    damage = int(damage * def_status.damage_taken_mult)

    if def_status.absorb_pct > 0:
        reveal_hidden_dodge(def_status, ctx)
        reduced = int(damage * (100 - def_status.absorb_pct) / 100)
        ctx.effect(f"Поглощение {def_status.absorb_pct}%: −{reduced} HP")
        damage = reduced
        def_status.absorb_pct = 0

    hp = state.hp_for(defender_id)
    state.set_hp_for(defender_id, hp - damage)
    if damage > 0:
        ctx.damage = damage
        ctx.damage_target_id = defender_id
    return damage


def _set_battle_loh(state: BattleState, user_id: int) -> int:
    if user_id == state.p1_id:
        state.p1_character = "loh"
    else:
        state.p2_character = "loh"
    return user_id


def apply_beam_response(
    state: BattleState,
    victim_id: int,
    action_id: str,
    roll: int,
) -> ActionResult:
    """Реакция жертвы после попадания луча Солдатика."""
    ctx = _ActionCtx(roll=roll, action_id=action_id, actor_id=victim_id)
    attacker_id = state.beam_response_attacker_id or state.opponent_id(victim_id)
    demote_id: int | None = None

    if action_id == "beam_dodge":
        ctx.effect("Попытка увернуться от луча…")
        if roll == 6:
            _apply_damage(state, attacker_id, victim_id, 30, ctx)
            ctx.effect("Уворот удался — луч задел, −30 HP. Способности сохранены!")
        else:
            _apply_damage(state, attacker_id, victim_id, 50, ctx)
            ctx.effect("Неудача — лучевой удар: −50 HP, потеря способностей.")
            demote_id = _set_battle_loh(state, victim_id)
    elif action_id == "beam_counter":
        if roll <= 3:
            dmg = 7
        elif roll <= 5:
            dmg = 15
        else:
            dmg = 20
        _apply_damage(state, victim_id, attacker_id, dmg, ctx)
        ctx.effect(f"Контратака: −{dmg} HP.")
        _apply_damage(state, attacker_id, victim_id, 50, ctx)
        ctx.effect("Луч всё равно попал: −50 HP. Способности потеряны.")
        demote_id = _set_battle_loh(state, victim_id)
    else:
        ctx.effect("Неизвестная реакция.")

    state.beam_response_user_id = None
    state.beam_response_attacker_id = None

    win = _check_win(state)
    if win:
        win.turn_report = ctx.to_report()
        win.demote_to_loh_user_id = demote_id
        return win

    _switch_turn(state)
    return ActionResult(
        turn_report=ctx.to_report(),
        demote_to_loh_user_id=demote_id,
    )


def _check_win(state: BattleState) -> ActionResult | None:
    if state.p1_hp <= 0:
        return ActionResult(ended=True, winner_id=state.p2_id, loser_id=state.p1_id)
    if state.p2_hp <= 0:
        return ActionResult(ended=True, winner_id=state.p1_id, loser_id=state.p2_id)
    return None


def _switch_turn(state: BattleState) -> None:
    outgoing_id = state.turn_user_id
    state.turn_user_id = (
        state.p2_id if state.turn_user_id == state.p1_id else state.p1_id
    )
    _tick_status_turn_end(state.status_for(outgoing_id))
    begin_turn(state)


def begin_turn(state: BattleState) -> None:
    """Тик кулдаунов и статусов в начале хода игрока."""
    _tick_status_turn_start(state.status_for(state.turn_user_id))


def _finish(ctx: _ActionCtx, state: BattleState, **kwargs) -> ActionResult:
    reveal_dodger_before_opponent_turn(state, ctx.actor_id, ctx)
    win = _check_win(state)
    if win:
        win.turn_report = ctx.to_report()
        return win
    _switch_turn(state)
    return ActionResult(turn_report=ctx.to_report(), **kwargs)


def apply_action(
    state: BattleState,
    actor_id: int,
    action_id: str,
    roll: int,
    *,
    actor_v_tier: str = "none",
    opponent_v_tier: str = "none",
    extra_rolls: list[int] | None = None,
) -> ActionResult:
    ctx = _ActionCtx(roll=roll, action_id=action_id, actor_id=actor_id)
    if extra_rolls:
        ctx.extra_rolls = list(extra_rolls)
    character = (
        state.p1_character if actor_id == state.p1_id else state.p2_character
    )
    opp_id = state.opponent_id(actor_id)
    opp_char = (
        state.p2_character if opp_id == state.p2_id else state.p1_character
    )
    status = state.status_for(actor_id)
    opp_status = state.status_for(opp_id)

    if action_disabled(action_id, status, character):
        return ActionResult()

    if action_id.startswith("bbc_"):
        from game.battle_billy_comics import apply_billy_comics_action

        comics_result = apply_billy_comics_action(
            ctx,
            state,
            actor_id,
            opp_id,
            ctx.extra_rolls,
            apply_damage=_apply_damage,
            finish=_finish,
            opp_char=opp_char,
        )
        if comics_result is not None:
            return comics_result

    if character == "mimic":
        from game.battle_mimic import apply_mimic_action

        def _mimic_delegate(
            st: BattleState,
            aid_actor: int,
            copied_id: str,
            dice_roll: int,
            *,
            extra_rolls: list[int] | None = None,
        ) -> ActionResult:
            return apply_action(
                st,
                aid_actor,
                copied_id,
                dice_roll,
                actor_v_tier=actor_v_tier,
                opponent_v_tier=opponent_v_tier,
                extra_rolls=extra_rolls,
            )

        mimic_result = apply_mimic_action(
            ctx,
            state,
            actor_id,
            opp_id,
            ctx.extra_rolls,
            apply_damage=_apply_damage,
            finish=_finish,
            apply_action_delegate=_mimic_delegate,
        )
        if mimic_result is not None:
            return mimic_result

    from game.battle_noir import apply_noir_action

    noir_result = apply_noir_action(
        ctx,
        state,
        actor_id,
        opp_id,
        ctx.extra_rolls,
        apply_damage=_apply_damage,
        finish=_finish,
        switch_turn=_switch_turn,
    )
    if noir_result is not None:
        return noir_result

    from game.characters import is_comics_action

    if character == "butcher_billy_comics" or is_comics_action(action_id):
        from game.battle_billy_comics import apply_billy_comics_action

        comics_result = apply_billy_comics_action(
            ctx,
            state,
            actor_id,
            opp_id,
            ctx.extra_rolls,
            apply_damage=_apply_damage,
            finish=_finish,
            opp_char=opp_char,
        )
        if comics_result is not None:
            return comics_result

    from game.battle_actions_new import apply_new_character_action

    new_result = apply_new_character_action(
        ctx,
        state,
        actor_id,
        opp_id,
        ctx.extra_rolls,
        apply_damage=_apply_damage,
        finish=_finish,
        check_win=_check_win,
        switch_turn=_switch_turn,
    )
    if new_result is not None:
        return new_result

    if action_id == "loh_punch":
        dmg = 15 if roll == 6 else 5
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
    elif action_id == "loh_dodge":
        from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

        if roll == 6:
            register_hidden_dodge(status, ["Уворот удался!"], dodge_active=True)
        else:
            _apply_damage(state, actor_id, actor_id, 5, ctx, ignore_dodge=True)
            register_hidden_dodge(status, ["Уворот не удался — по ебалу."])
        mark_dodge_turn_hidden(ctx)
    elif action_id == "hl_laser":
        dmg = DAMAGE_TABLE_LASER.get(roll, 10)
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "hl_laser", 2)
        ctx.effect("Лазер: кулдаун 2 хода.")
    elif action_id == "hl_punch":
        dmg = DAMAGE_TABLE_STANDARD.get(roll, 7)
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
    elif action_id == "hl_scorched":
        if status.scorched_pct >= 100:
            status.scorched_pct = 0
            ctx.effect("Выжженная земля выпущена!")
            if roll <= 4:
                dmg = 35
                opp_status.dodge_forbidden_turns = 1
                ctx.effect("Уворот противника заблокирован на 1 ход!")
            else:
                dmg = 40
                pool = [
                    a
                    for a in get_actions_for_character(opp_char)
                    if a.kind not in ("passive_info",)
                ]
                if pool:
                    blocked = random.choice(pool)
                    opp_status.anti_v_disabled = [blocked.id]
                    opp_status.ability_block_turns = 1
                    ctx.effect(
                        f"Способность «{blocked.label}» заблокирована на 1 ход!"
                    )
            _apply_damage(state, actor_id, opp_id, dmg, ctx)
        else:
            add = SCORCHED_CHARGE.get(roll, 20)
            status.scorched_pct = min(100, status.scorched_pct + add)
            ctx.effect(f"Выжженная земля: {status.scorched_pct}%")
            if status.scorched_pct >= 100:
                ctx.effect("Готово к выпуску на следующем нажатии!")
            _switch_turn(state)
            return ActionResult(turn_report=ctx.to_report())
    elif action_id == "hl_dodge":
        from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

        if roll % 2 == 0:
            register_hidden_dodge(status, ["Увернулся!"], dodge_active=True)
        else:
            _apply_damage(state, actor_id, actor_id, 5, ctx, ignore_dodge=True)
            register_hidden_dodge(status, ["По ебалу."])
        mark_dodge_turn_hidden(ctx)
    elif action_id == "hl_flight":
        if roll >= 5:
            ctx.effect("Сбежал с поля боя!")
            return ActionResult(
                turn_report=ctx.to_report(),
                ended=True,
                escaped_user_id=actor_id,
            )
        ctx.effect("Не удалось сбежать.")
    elif action_id == "sl_punch":
        dmg = DAMAGE_TABLE_STAR_PUNCH.get(roll, 7)
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
    elif action_id == "sl_charges":
        base = 5 if roll <= 3 else 7
        r2 = (extra_rolls or [1])[0]
        ctx.extra_rolls = [r2]
        if r2 <= 3:
            mult = 2
        elif r2 <= 5:
            mult = 3
        else:
            mult = 4
        dmg = base * mult
        ctx.effect(f"Звёздные заряды: {base}×{mult} = {dmg} HP!")
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "sl_charges", 2)
        ctx.effect("Кулдаун 2 хода.")
    elif action_id == "sl_flight":
        from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

        if roll <= 3:
            register_hidden_dodge(status, ["Полёт-уворот: неудача."])
        elif roll <= 5:
            register_hidden_dodge(
                status, ["Полёт-уворот: увернулась!"], dodge_active=True
            )
        else:
            opp_status.miss_chance = max(opp_status.miss_chance, 0.3)
            register_hidden_dodge(
                status,
                [
                    "Полёт-уворот: увернулась!",
                    "Контрослепление: 30% промах противнику на 1 ход!",
                ],
                dodge_active=True,
            )
        mark_dodge_turn_hidden(ctx)
    elif action_id == "sl_heavy":
        if status.star_charged_pct >= 100:
            status.star_charged_pct = 0
            if roll <= 4:
                dmg = 20
                opp_status.miss_chance = max(opp_status.miss_chance, 0.3)
                ctx.effect("Оглушение: 30% промах противнику!")
            else:
                dmg = 30
                opp_status.miss_chance = max(opp_status.miss_chance, 0.5)
                ctx.effect("Оглушение: 50% промах противнику!")
            _apply_damage(state, actor_id, opp_id, dmg, ctx, ignore_dodge=True)
        else:
            add = STAR_HEAVY_CHARGE.get(roll, 20)
            status.star_charged_pct = min(100, status.star_charged_pct + add)
            ctx.effect(f"Тяжёлый заряженный удар: {status.star_charged_pct}%")
            if status.star_charged_pct >= 100:
                ctx.effect("Готово к выпуску на следующем нажатии!")
            _switch_turn(state)
            return ActionResult(turn_report=ctx.to_report())
    elif action_id == "sl_ult":
        if roll % 2 == 0:
            opp_status.blind_turns = 1
            ctx.effect("Звёздный свет: ослепление 1 ход.")
        else:
            opp_status.miss_chance = 0.9
            ctx.effect("Звёздный свет: 90% промах врагу.")
        set_ability_cooldown(status, "sl_ult", 3)
        ctx.effect("Кулдаун 3 хода.")
    elif action_id == "sb_punch":
        dmg = DAMAGE_TABLE_STANDARD.get(roll, 7)
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
    elif action_id == "sb_bullet":
        dmg = DAMAGE_TABLE_SB_BULLET.get(roll, 11)
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
        set_ability_cooldown(status, "sb_bullet", 2)
        ctx.effect("Пулевой выстрел: кулдаун 2 хода.")
    elif action_id == "sb_beam":
        if status.soldier_beam_pct >= 100:
            status.soldier_beam_pct = 0
            if opp_char == "loh":
                ctx.effect("Луч по Лоху — защиты нет, −100 HP!")
                _apply_damage(state, actor_id, opp_id, 100, ctx)
                win = _check_win(state)
                if win:
                    win.turn_report = ctx.to_report()
                    win.send_soldier_beam_sticker = True
                    return win
                return _finish(
                    ctx, state, send_soldier_beam_sticker=True
                )
            state.beam_response_user_id = opp_id
            state.beam_response_attacker_id = actor_id
            state.turn_user_id = opp_id
            ctx.effect("Луч заряжен! Жертва — выбери реакцию до удара.")
            win = _check_win(state)
            if win:
                win.turn_report = ctx.to_report()
                win.send_soldier_beam_sticker = True
                return win
            return ActionResult(
                turn_report=ctx.to_report(),
                send_soldier_beam_sticker=True,
            )
        add = BEAM_CHARGE.get(roll, 20)
        status.soldier_beam_pct = min(100, status.soldier_beam_pct + add)
        set_ability_cooldown(status, "sb_beam", 1)
        ctx.effect(f"Лучевой удар: {status.soldier_beam_pct}%")
        ctx.effect("Накопление: кулдаун 1 ход.")
        _switch_turn(state)
        return ActionResult(turn_report=ctx.to_report())
    elif action_id == "sb_beam_charge":
        add = BEAM_CHARGE.get(roll, 20)
        status.soldier_beam_pct = min(100, status.soldier_beam_pct + add)
        set_ability_cooldown(status, "sb_beam_charge", 1)
        ctx.effect(f"Луч заряжен: {status.soldier_beam_pct}%")
        ctx.effect("Накопление луча: кулдаун 1 ход.")
        _switch_turn(state)
        return ActionResult(turn_report=ctx.to_report())
    elif action_id == "sb_shield_rush":
        from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

        r = roll
        if r <= 3:
            _apply_damage(state, actor_id, actor_id, 5, ctx, ignore_dodge=True)
            register_hidden_dodge(status, ["Рывок с щитом: не увернулся."])
        elif r == 4:
            _apply_damage(state, actor_id, opp_id, 5, ctx)
            register_hidden_dodge(
                status,
                ["Рывок с щитом: защита, контрудар 5 HP!"],
                dodge_active=True,
            )
        elif r == 5:
            _apply_damage(state, actor_id, opp_id, 10, ctx)
            register_hidden_dodge(
                status,
                ["Рывок с щитом: защита, контрудар 10 HP!"],
                dodge_active=True,
            )
        else:
            _apply_damage(state, actor_id, opp_id, 15, ctx)
            register_hidden_dodge(
                status,
                ["Рывок с щитом: защита, контрудар 15 HP!"],
                dodge_active=True,
            )
        mark_dodge_turn_hidden(ctx)
    elif action_id == "sb_beam_fire":
        if status.soldier_beam_pct >= 100:
            status.soldier_beam_pct = 0
            if opp_char == "loh":
                ctx.effect("Луч по Лоху — защиты нет, −100 HP!")
                _apply_damage(state, actor_id, opp_id, 100, ctx)
                win = _check_win(state)
                if win:
                    win.turn_report = ctx.to_report()
                    win.send_soldier_beam_sticker = True
                    return win
                return _finish(
                    ctx, state, send_soldier_beam_sticker=True
                )
            state.beam_response_user_id = opp_id
            state.beam_response_attacker_id = actor_id
            state.turn_user_id = opp_id
            ctx.effect("Луч заряжен! Жертва — выбери реакцию до удара.")
            win = _check_win(state)
            if win:
                win.turn_report = ctx.to_report()
                win.send_soldier_beam_sticker = True
                return win
            return ActionResult(
                turn_report=ctx.to_report(),
                send_soldier_beam_sticker=True,
            )
        else:
            ctx.effect("Луч не заряжен (нужно 100%).")
    elif action_id == "sb_escape":
        if roll <= 4:
            ok = False
        elif roll == 5:
            ok = not is_super_tier(actor_v_tier)
        else:
            ok = True
        if ok:
            ctx.effect("Сбежал!")
            return ActionResult(
                turn_report=ctx.to_report(),
                ended=True,
                escaped_user_id=actor_id,
            )
        ctx.effect("Не сбежал.")
    elif action_id == "sf_lightning":
        dmg = DAMAGE_TABLE_SF_LIGHTNING.get(roll, 9)
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
        if roll == 5:
            status.damage_dealt_mult = 1.15
            status.dealt_mult_turns = 1
            ctx.effect("Бонус +15% урона на следующий ход!")
        elif roll == 6:
            opp_status.stunned = 1
            ctx.effect("Оглушение: противник пропускает ход!")
        set_ability_cooldown(status, "sf_lightning", 2)
        ctx.effect("Град Молний: кулдаун 2 хода.")
    elif action_id == "sf_punch":
        dmg = DAMAGE_TABLE_STRIKE_S.get(roll, 5)
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
    elif action_id == "sf_storm":
        if status.storm_pct >= 100:
            status.storm_pct = 0
            ctx.effect("Буря выпущена!")
            if roll <= 4:
                dmg = 40
            else:
                dmg = 50
            _apply_damage(state, actor_id, opp_id, dmg, ctx)
        else:
            add = STORM_CHARGE.get(roll, 20)
            status.storm_pct = min(100, status.storm_pct + add)
            ctx.effect(f"Буря: {status.storm_pct}%")
            if status.storm_pct >= 100:
                ctx.effect("Готово к выпуску на следующем нажатии!")
            _switch_turn(state)
            return ActionResult(turn_report=ctx.to_report())
    elif action_id == "sf_dodge":
        from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

        if roll <= 3:
            register_hidden_dodge(status, ["Уворот: неудача."])
        else:
            lines = ["Уворот: удачно!"]
            if roll == 4:
                add = 5
            elif roll == 5:
                add = 7
            else:
                add = 10
            status.storm_pct = min(100, status.storm_pct + add)
            lines.append(f"Буря: +{add}% (всего {status.storm_pct}%).")
            register_hidden_dodge(status, lines, dodge_active=True)
        mark_dodge_turn_hidden(ctx)
    elif action_id == "bu_punch":
        dmg = DAMAGE_TABLE_STANDARD.get(roll, 7)
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
    elif action_id == "bu_barrage":
        base = 5 if roll <= 3 else 7
        r2 = (extra_rolls or [1])[0]
        ctx.extra_rolls = [r2]
        mult = 2 if r2 <= 3 else (3 if r2 <= 5 else 4)
        dmg = base * mult
        ctx.effect(f"Взрывной шквал: {base}×{mult} = {dmg} HP!")
        _apply_damage(state, actor_id, opp_id, dmg, ctx)
        if r2 == 6:
            opp_status.miss_chance = max(opp_status.miss_chance, 0.5)
            ctx.effect("Сотрясение мозга: 50% промах противнику на 1 ход!")
        set_ability_cooldown(status, "bu_barrage", 2)
        ctx.effect("Кулдаун 2 хода.")
    elif action_id == "bu_rush":
        if status.rush_pct >= 100:
            status.rush_pct = 0
            ctx.effect("Разрушительный рывок выпущен!")
            if roll <= 5:
                dmg = 40
            else:
                dmg = 45
                opp_status.miss_chance = max(opp_status.miss_chance, 0.7)
                ctx.effect("Оглушающий удар: 70% промах противнику на 1 ход!")
            _apply_damage(state, actor_id, opp_id, dmg, ctx)
        else:
            add = BUTCHER_RUSH_CHARGE.get(roll, 25)
            status.rush_pct = min(100, status.rush_pct + add)
            ctx.effect(f"Разрушительный рывок: {status.rush_pct}%")
            if status.rush_pct >= 100:
                ctx.effect("Готово к выпуску на следующем нажатии!")
            _switch_turn(state)
            return ActionResult(turn_report=ctx.to_report())
    elif action_id == "bu_flight":
        from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

        if roll <= 3:
            register_hidden_dodge(status, ["Полёт-уворот: неудача."])
        elif roll == 4:
            status.damage_dealt_mult = 1.1
            status.dealt_mult_turns = 1
            register_hidden_dodge(
                status,
                ["Полёт-уворот: увернулся, растрескал землю (+10% урона)!"],
                dodge_active=True,
            )
        else:
            register_hidden_dodge(
                status,
                ["Полёт-уворот: защита, контратака 7 HP!"],
                dodge_active=True,
            )
            _apply_damage(state, actor_id, opp_id, 7, ctx)
        mark_dodge_turn_hidden(ctx)
    elif action_id == "sf_storm_charge":
        add = STORM_CHARGE.get(roll, 20)
        status.storm_pct = min(100, status.storm_pct + add)
        ctx.effect(f"Буря: {status.storm_pct}%")
        _switch_turn(state)
        return ActionResult(turn_report=ctx.to_report())
    elif action_id == "sf_storm_fire":
        if status.storm_pct >= 100:
            _apply_damage(state, actor_id, opp_id, 40, ctx)
            status.storm_pct = 0
        else:
            ctx.effect("Буря не готова.")
    elif action_id == "battle_escape":
        if roll >= 5:
            ctx.effect("Сбежал с поля боя!")
            return ActionResult(
                turn_report=ctx.to_report(),
                ended=True,
                escaped_user_id=actor_id,
            )
        ctx.effect("Не удалось сбежать.")
    elif action_id == "item_virus":
        if opponent_v_tier == "v1":
            opp_status.stunned = 1
            ctx.effect("V1: вирус оглушает на 1 ход!")
        elif is_super_tier(opponent_v_tier) or opp_char != "loh":
            prev_hp = state.hp_for(opp_id)
            state.set_hp_for(opp_id, 0)
            ctx.damage = prev_hp
            ctx.damage_target_id = opp_id
            ctx.effect("Вирус убил супера! Способности потеряны.")
            win = _check_win(state)
            if win:
                win.turn_report = ctx.to_report()
                win.virus_victim_id = opp_id
                return win
            return ActionResult(
                turn_report=ctx.to_report(),
                virus_victim_id=opp_id,
            )
        else:
            _apply_damage(state, actor_id, opp_id, 30, ctx)
            ctx.effect("Вирус по обычному противнику.")
    else:
        ctx.effect("Неизвестное действие.")

    return _finish(ctx, state)


def process_turn_start(status: PlayerBattleStatus) -> list[str]:
    return _tick_status_turn_start(status)


def needs_skip_turn(state: BattleState, user_id: int) -> bool:
    return state.status_for(user_id).stunned > 0
