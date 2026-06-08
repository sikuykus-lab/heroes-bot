"""Мимик (V1) — копирование и случайные способности."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Callable

from game.characters import (
    CHARACTER_NAMES,
    CHARACTERS_BY_TIER,
    SECRET_V_CHARACTERS,
    get_action_label,
    get_actions_for_character,
)
from game.dodge_hidden import mark_dodge_turn_hidden, register_hidden_dodge

if TYPE_CHECKING:
    from game.battle_engine import ActionResult, _ActionCtx
    from game.models import BattleState

MIMIC_NATIVE_ACTIONS = frozenset(
    {"mm_random", "mm_copy1", "mm_copy2", "mm_reroll", "mm_dodge"}
)

NON_COPY_LABELS = frozenset({"Удар", "Усиленный удар", "Побег", "Сдача"})

NON_COPY_KINDS = frozenset({"escape", "escape_sb", "once_battle"})


def copyable_action_pool(opp_character: str) -> list[str]:
    pool: list[str] = []
    for act in get_actions_for_character(opp_character):
        if act.id in MIMIC_NATIVE_ACTIONS:
            continue
        if act.label in NON_COPY_LABELS:
            continue
        if act.kind in NON_COPY_KINDS:
            continue
        pool.append(act.id)
    return pool


def _v24_mimic_copy_pool() -> list[str]:
    """Пул копий для боя мимик vs мимик — способности случайных V24-героев."""
    pool: list[str] = []
    for char in CHARACTERS_BY_TIER.get("v24", set()):
        pool.extend(copyable_action_pool(char))
    return list(dict.fromkeys(pool))


def _mimic_vs_mimic_pool() -> list[str]:
    return _v24_mimic_copy_pool()


def _copy_source_label(opp_character: str) -> str:
    if opp_character == "mimic":
        return "случайный V24"
    if opp_character in SECRET_V_CHARACTERS:
        return CHARACTER_NAMES.get(opp_character, opp_character)
    return CHARACTER_NAMES.get(opp_character, opp_character)


def _pick_from_random_v24(exclude: set[str]) -> str:
    chars = list(CHARACTERS_BY_TIER.get("v24", set()))
    random.shuffle(chars)
    for char in chars:
        pool = [a for a in copyable_action_pool(char) if a not in exclude]
        if pool:
            return random.choice(pool)
    return ""


def _reroll_pool(opp_character: str) -> list[str]:
    if opp_character == "mimic":
        return _v24_mimic_copy_pool()
    return copyable_action_pool(opp_character)


def _pick_two_reroll_copies(
    opp_character: str, prev_c1: str, prev_c2: str
) -> tuple[str, str]:
    """Две новые копии; по возможности отличаются от прежних и друг от друга."""
    pool = _reroll_pool(opp_character)
    if len(pool) >= 2:
        prev = {p for p in (prev_c1, prev_c2) if p}
        fresh = [a for a in pool if a not in prev]
        if len(fresh) >= 2:
            return random.sample(fresh, 2)
        if len(fresh) == 1:
            c1 = fresh[0]
            others = [a for a in pool if a != c1]
            c2 = random.choice(others) if others else c1
            return c1, c2
        return random.sample(pool, 2)
    if len(pool) == 1:
        return pool[0], pool[0]
    return "", ""


def _pick_two_copies(
    opp_character: str, exclude: set[str] | None = None
) -> tuple[str, str]:
    ex = exclude or set()
    if opp_character == "mimic":
        c1 = _pick_from_random_v24(ex)
        ex2 = ex | ({c1} if c1 else set())
        c2 = _pick_from_random_v24(ex2)
        return c1, c2
    pool = [a for a in copyable_action_pool(opp_character) if a not in ex]
    if len(pool) >= 2:
        picked = random.sample(pool, 2)
        return picked[0], picked[1]
    if len(pool) == 1:
        return pool[0], ""
    return "", ""


def init_mimic_for_battle(state: BattleState) -> list[str]:
    """Копирование при старте боя."""
    lines: list[str] = []
    for uid, char_key in (
        (state.p1_id, state.p1_character),
        (state.p2_id, state.p2_character),
    ):
        if char_key != "mimic":
            continue
        opp_char = (
            state.p2_character if uid == state.p1_id else state.p1_character
        )
        st = state.status_for(uid)
        c1, c2 = _pick_two_copies(opp_char)
        st.mimic_copy_1 = c1
        st.mimic_copy_2 = c2
        src = _copy_source_label(opp_char)
        if c1:
            lines.append(f"Мимик: копия 1 — {get_action_label(c1)} ({src})")
        if c2:
            lines.append(f"Мимик: копия 2 — {get_action_label(c2)} ({src})")
    return lines


def resolve_mimic_action_id(action_id: str, status) -> str | None:  # noqa: ANN001
    if action_id == "mm_copy1":
        return status.mimic_copy_1 or None
    if action_id == "mm_copy2":
        return status.mimic_copy_2 or None
    return None


def mimic_effective_action_id(
    action_id: str, status, character: str
) -> str:  # noqa: ANN001
    if character != "mimic":
        return action_id
    resolved = resolve_mimic_action_id(action_id, status)
    return resolved if resolved else action_id


def apply_mimic_action(
    ctx: _ActionCtx,
    state: BattleState,
    actor_id: int,
    opp_id: int,
    extra_rolls: list[int],
    *,
    apply_damage,
    finish,
    apply_action_delegate: Callable[..., ActionResult],
) -> ActionResult | None:
    """Уникальные способности Мимика. None — не обработано."""
    aid = ctx.action_id
    if aid not in MIMIC_NATIVE_ACTIONS:
        return None

    status = state.status_for(actor_id)
    opp_char = (
        state.p2_character if opp_id == state.p2_id else state.p1_character
    )

    if aid in ("mm_copy1", "mm_copy2"):
        copied = resolve_mimic_action_id(aid, status)
        if not copied:
            ctx.effect("Копирование пусто.")
            return finish(ctx, state)
        return apply_action_delegate(
            state,
            actor_id,
            copied,
            ctx.roll,
            extra_rolls=extra_rolls,
        )

    if aid == "mm_random":
        return _mimic_random_strike(
            ctx, state, actor_id, opp_id, extra_rolls, apply_damage, finish
        )

    if aid == "mm_reroll":
        c1, c2 = _pick_two_reroll_copies(
            opp_char, status.mimic_copy_1, status.mimic_copy_2
        )
        status.mimic_copy_1 = c1
        status.mimic_copy_2 = c2
        ctx.effect("Смена способностей: новые копии!")
        if c1:
            ctx.effect(f"Копия 1: {get_action_label(c1)}")
        if c2:
            ctx.effect(f"Копия 2: {get_action_label(c2)}")
        return finish(ctx, state)

    if aid == "mm_dodge":
        return _mimic_random_dodge(
            ctx, state, actor_id, opp_id, apply_damage, finish
        )

    return None


def _mimic_random_strike(
    ctx: _ActionCtx,
    state: BattleState,
    actor_id: int,
    opp_id: int,
    extra_rolls: list[int],
    apply_damage,
    finish,
) -> ActionResult:
    opp_status = state.status_for(opp_id)
    actor_status = state.status_for(actor_id)
    r = ctx.roll
    opp_char = (
        state.p2_character if opp_id == state.p2_id else state.p1_character
    )

    if r == 1:
        apply_damage(state, actor_id, opp_id, 7, ctx)
        opp_status.stunned = 1
        ctx.effect("Оглушение противника на 1 ход!")
    elif r == 2:
        apply_damage(state, actor_id, opp_id, 9, ctx)
        apply_damage(state, actor_id, opp_id, 5, ctx)
        ctx.effect("Второй удар ногой: +5 HP!")
    elif r == 3:
        apply_damage(state, actor_id, opp_id, 15, ctx)
        opp_status.blind_turns = 1
        ctx.effect("Ослепление противника на 1 ход!")
    elif r == 4:
        apply_damage(state, actor_id, opp_id, 18, ctx)
        r2 = (extra_rolls or [1])[0]
        ctx.extra_rolls = [r2]
        if r2 % 2 == 0:
            register_hidden_dodge(
                actor_status,
                ["Случайный удар: телепорт-уворот на ход!"],
                dodge_active=True,
            )
            mark_dodge_turn_hidden(ctx)
            ctx.effect(f"Второй кубик {r2} (чёт): телепорт-уворот!")
        else:
            actor_status.absorb_pct = 30
            ctx.effect(f"Второй кубик {r2} (нечёт): поглощение 30% на ход!")
    elif r == 5:
        apply_damage(state, actor_id, opp_id, 20, ctx)
        apply_damage(state, actor_id, opp_id, 3, ctx)
        opp_status.miss_chance = max(opp_status.miss_chance, 0.2)
        ctx.effect("Мини-молния: +3 HP, 20% промах врагу на ход!")
    else:
        apply_damage(state, actor_id, opp_id, 25, ctx)
        pool = [
            a
            for a in get_actions_for_character(opp_char)
            if a.kind not in ("passive_info",)
            and a.id not in MIMIC_NATIVE_ACTIONS
        ]
        if pool:
            blocked = random.choice(pool)
            opp_status.anti_v_disabled = [blocked.id]
            opp_status.ability_block_turns = 1
            ctx.effect(f"Блокировка «{blocked.label}» на 1 ход!")

    return finish(ctx, state)


def _mimic_random_dodge(
    ctx: _ActionCtx,
    state: BattleState,
    actor_id: int,
    opp_id: int,
    apply_damage,
    finish,
) -> ActionResult:
    status = state.status_for(actor_id)
    r = ctx.roll

    if r == 1:
        register_hidden_dodge(status, ["Случайный уворот: неудача."])
    elif r == 2:
        register_hidden_dodge(
            status,
            ["Случайный уворот: увернулся, контрудар 7 HP!"],
            dodge_active=True,
        )
        apply_damage(state, actor_id, opp_id, 7, ctx)
    elif r == 3:
        register_hidden_dodge(status, ["Случайный уворот: неудача."])
    elif r == 4:
        register_hidden_dodge(
            status,
            ["Случайный уворот: увернулся, лазер 9 HP!"],
            dodge_active=True,
        )
        apply_damage(state, actor_id, opp_id, 9, ctx)
    elif r == 5:
        register_hidden_dodge(status, ["Случайный уворот: неудача."])
    else:
        register_hidden_dodge(
            status,
            ["Случайный уворот: тяжёлый удар 12 HP!"],
            dodge_active=True,
        )
        apply_damage(state, actor_id, opp_id, 12, ctx)
        status.damage_taken_mult = 1.15
        status.taken_mult_turns = 1
        ctx.effect("Уязвимость: +15% получаемого урона на 1 ход!")

    mark_dodge_turn_hidden(ctx)
    return finish(ctx, state)
