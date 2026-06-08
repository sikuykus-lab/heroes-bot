"""Персонажи, способности и таблицы урона."""

from __future__ import annotations

import random
from dataclasses import dataclass

# id -> отображаемое имя
CHARACTER_NAMES: dict[str, str] = {
    "loh": "Лох",
    "loh_full": "Полный Лох",
    "homelander": "Хоумлендер",
    "starlight": "Звёздочка",
    "soldier_boy": "Солдатик",
    "stormfront": "Штормфронт",
    "butcher": "Бомбсайт",
    "butcher_william": "Уильям Бутчер",
    "butcher_billy": "Билли Бутчер",
    "a_train": "А-Трейн",
    "newman": "Ньюман",
    "teleporter": "Телепорт",
    "butcher_billy_comics": "Билли Бутчер Comics",
    "mimic": "Мимик",
    "black_noir": "Чёрный Нуар",
    "flying_noir": "Летающий Нуар",
}

# tier -> доступные персонажи (Лох только без V)
CHARACTERS_BY_TIER: dict[str, set[str]] = {
    "none": {"loh"},
    "v14bb": {"loh_full"},
    "v24": {
        "homelander",
        "starlight",
        "butcher_william",
        "a_train",
        "newman",
        "teleporter",
        "flying_noir",
    },
    "v": {
        "homelander",
        "starlight",
        "butcher_billy",
        "a_train",
        "newman",
        "teleporter",
        "flying_noir",
    },
    "v1": {"soldier_boy", "stormfront", "butcher", "mimic", "black_noir"},
    "secret_v": {"butcher_billy_comics"},
}

SECRET_V_CHARACTERS: frozenset[str] = frozenset({"butcher_billy_comics"})


def tier_allows_character(v_tier: str, character: str) -> bool:
    allowed = CHARACTERS_BY_TIER.get(v_tier, CHARACTERS_BY_TIER["none"])
    return character in allowed


def random_character_for_tier(v_tier: str) -> str:
    """Случайный супергерой из пула tier (V24/V/V1 — только рандом)."""
    if v_tier in ("none", "secret_v"):
        return "loh"
    pool = list(CHARACTERS_BY_TIER.get(v_tier, {"loh"}))
    return random.choice(pool)


def resolve_battle_character(v_tier: str, active_character: str) -> str:
    """Персонаж в бою с учётом уровня V."""
    if v_tier == "none":
        return "loh"
    if v_tier == "v14bb":
        return "loh_full"
    if v_tier == "secret_v":
        if active_character in SECRET_V_CHARACTERS:
            return active_character
        return "butcher_billy_comics"
    if tier_allows_character(v_tier, active_character):
        return active_character
    return random_character_for_tier(v_tier)


def apply_super_promotion(player, *, roll: bool = False) -> None:  # noqa: ANN001
    """Снять Лох; при roll=True — новый случайный герой для текущего V."""
    if player.v_tier == "none":
        player.active_character = "loh"
        return
    if player.v_tier == "v14bb":
        player.active_character = "loh_full"
        return
    if player.v_tier == "secret_v":
        if player.active_character not in SECRET_V_CHARACTERS:
            player.active_character = "butcher_billy_comics"
        return
    if roll:
        player.active_character = random_character_for_tier(player.v_tier)
        return
    if player.active_character == "loh" or not tier_allows_character(
        player.v_tier, player.active_character
    ):
        player.active_character = random_character_for_tier(player.v_tier)


def player_status_label(v_tier: str, active_character: str) -> str:
    if v_tier == "none":
        return "Лох"
    if v_tier == "v14bb":
        return "V14BB · Полный Лох"
    if v_tier == "secret_v":
        return f"Secret V · {CHARACTER_NAMES.get(active_character, active_character)}"
    return CHARACTER_NAMES.get(active_character, active_character)


def counts_battle_stats(v_tier: str) -> bool:
    """Учитывать победы/поражения в профиле."""
    return v_tier != "secret_v"


# tier V при выдаче персонажа админом
ADMIN_CHARACTER_TIER: dict[str, str] = {
    "loh": "none",
    "loh_full": "v14bb",
    "homelander": "v",
    "starlight": "v",
    "soldier_boy": "v1",
    "stormfront": "v1",
    "butcher": "v1",
    "mimic": "v1",
    "black_noir": "v1",
    "flying_noir": "v24",
    "butcher_william": "v24",
    "butcher_billy": "v",
    "a_train": "v24",
    "newman": "v24",
    "teleporter": "v24",
    "butcher_billy_comics": "secret_v",
}

ALL_CHARACTER_IDS: list[str] = list(CHARACTER_NAMES.keys())


def admin_assign_character(player, character: str) -> None:  # noqa: ANN001
    player.active_character = character
    player.v_tier = ADMIN_CHARACTER_TIER.get(character, "none")
    player.v24_battles_left = 0


def admin_clear_hero(player) -> None:  # noqa: ANN001
    player.v_tier = "none"
    player.active_character = "loh"
    player.v24_battles_left = 0


def is_super_tier(v_tier: str) -> bool:
    return v_tier in ("v", "v24", "v1", "secret_v")


# Таблицы урона по значению кубика 1-6
DAMAGE_TABLE_STANDARD = {1: 7, 2: 9, 3: 11, 4: 15, 5: 20, 6: 25}
DAMAGE_TABLE_LASER = {1: 10, 2: 12, 3: 15, 4: 20, 5: 25, 6: 35}
DAMAGE_TABLE_PUNCH_H = {1: 5, 2: 7, 3: 9, 4: 15, 5: 17, 6: 19}
DAMAGE_TABLE_LIGHTNING = {1: 5, 2: 7, 3: 9, 4: 15, 5: 17, 6: 20}
DAMAGE_TABLE_STRIKE_S = {1: 5, 2: 7, 3: 9, 4: 15, 5: 17, 6: 19}
DAMAGE_TABLE_STAR_PUNCH = {1: 7, 2: 9, 3: 15, 4: 17, 5: 20, 6: 25}
STAR_HEAVY_CHARGE = {1: 20, 2: 20, 3: 20, 4: 33, 5: 33, 6: 50}

BEAM_CHARGE = {1: 20, 2: 23, 3: 26, 4: 30, 5: 35, 6: 50}
SCORCHED_CHARGE = {1: 25, 2: 30, 3: 35, 4: 40, 5: 45, 6: 50}
BUTCHER_RUSH_CHARGE = {1: 25, 2: 25, 3: 33, 4: 33, 5: 40, 6: 50}
DAMAGE_TABLE_SF_LIGHTNING = {1: 9, 2: 11, 3: 15, 4: 18, 5: 20, 6: 25}
STORM_CHARGE = {1: 20, 2: 20, 3: 20, 4: 33, 5: 33, 6: 40}
DAMAGE_TABLE_SB_BULLET = {1: 11, 2: 13, 3: 15, 4: 20, 5: 25, 6: 30}

DAMAGE_TABLE_WB_LASER = {1: 5, 2: 7, 3: 9, 4: 11, 5: 15, 6: 35}
DAMAGE_TABLE_AT_RUSH = {1: 7, 2: 11, 3: 15, 4: 19, 5: 22, 6: 25}
DAMAGE_TABLE_AT_RAPID_HIT = {1: 3, 2: 3, 3: 5, 4: 5, 5: 7, 6: 7}
DAMAGE_TABLE_NM_INTERNAL = {1: 10, 2: 12, 3: 14, 4: 16, 5: 18, 6: 20}
NEWMAN_TEAR_CHARGE = {1: 15, 2: 20, 3: 25, 4: 30, 5: 40, 6: 50}

ABSORB_TABLE = {1: 30, 2: 30, 3: 30, 4: 30, 5: 50, 6: 50}


@dataclass
class ActionDef:
    id: str
    label: str
    kind: str  # attack, dodge, escape, charge, skip_charge, ult_release, item


# Действия по персонажу
ACTIONS: dict[str, list[ActionDef]] = {
    "loh": [
        ActionDef("loh_punch", "Удар", "attack"),
        ActionDef("loh_dodge", "Уворот", "dodge"),
    ],
    "loh_full": [],
    "homelander": [
        ActionDef("hl_laser", "Лазерные глаза", "attack"),
        ActionDef("hl_punch", "Усиленный удар", "attack"),
        ActionDef("hl_scorched", "Выжженная земля", "scorched"),
        ActionDef("hl_dodge", "Уворот", "dodge"),
        ActionDef("hl_flight", "Полёт", "escape"),
    ],
    "starlight": [
        ActionDef("sl_punch", "Удар с ослеплением", "attack"),
        ActionDef("sl_charges", "Звёздные заряды", "attack_multi"),
        ActionDef("sl_flight", "Полёт-уворот", "dodge"),
        ActionDef("sl_heavy", "Тяжёлый заряженный удар", "star_heavy"),
        ActionDef("sl_ult", "Звёздный свет", "attack_ult"),
    ],
    "soldier_boy": [
        ActionDef("sb_punch", "Усиленный удар", "attack"),
        ActionDef("sb_bullet", "Пулевой выстрел", "attack"),
        ActionDef("sb_beam", "Лучевой удар", "charge_beam"),
        ActionDef("sb_shield_rush", "Рывок с щитом", "dodge"),
        ActionDef("sb_escape", "Побег", "escape_sb"),
    ],
    "stormfront": [
        ActionDef("sf_lightning", "Град Молний", "attack"),
        ActionDef("sf_punch", "Удар", "attack"),
        ActionDef("sf_storm", "Буря", "charge_storm"),
        ActionDef("sf_dodge", "Уворот", "dodge"),
    ],
    "butcher": [
        ActionDef("bu_punch", "Усиленный удар", "attack"),
        ActionDef("bu_barrage", "Взрывной шквал", "attack_multi"),
        ActionDef("bu_rush", "Разрушительный рывок", "charge_rush"),
        ActionDef("bu_flight", "Полёт-уворот", "dodge"),
    ],
    "butcher_william": [
        ActionDef("wb_punch", "Усиленный удар", "attack"),
        ActionDef("wb_laser", "Лазерные глаза", "attack"),
        ActionDef("wb_dash_dodge", "Рывковый уворот", "dodge"),
        ActionDef("wb_barrage", "Шквал ударов", "attack"),
    ],
    "butcher_billy": [
        ActionDef("bb_punch", "Усиленный удар", "attack"),
        ActionDef("bb_tentacle", "Удушение щупальцами", "attack"),
        ActionDef("bb_sensual_dodge", "Чувственный уворот", "dodge"),
        ActionDef("bb_crowbar", "Удар монтировкой", "attack"),
    ],
    "a_train": [
        ActionDef("at_punch", "Удар", "attack"),
        ActionDef("at_rush", "Скоростной напор", "attack"),
        ActionDef("at_rapid", "Ряд быстрых ударов", "attack_multi"),
        ActionDef("at_dodge", "Скоростной уворот", "dodge"),
        ActionDef("at_accel", "Ускорение", "buff"),
    ],
    "newman": [
        ActionDef("nm_punch", "Удар", "attack"),
        ActionDef("nm_internal", "Внутренний удар", "attack"),
        ActionDef("nm_tear", "Разрыв конечностей", "charge"),
        ActionDef("nm_head_explode", "Взрыв головы", "ult_release"),
        ActionDef("nm_regen_dodge", "Регенеративный уворот", "dodge"),
        ActionDef("nm_limb_weak", "Ослабление конечностей", "debuff"),
    ],
    "teleporter": [
        ActionDef("tp_punch", "Удар", "attack"),
        ActionDef("tp_barrage", "Ряд ударов телепортом", "attack"),
        ActionDef("tp_dodge", "Телепорт-уворот", "dodge"),
        ActionDef("tp_heavy", "Тяжёлый удар с телепортом", "attack"),
    ],
    "butcher_billy_comics": [
        ActionDef("bbc_laser", "Огненные лазерные глаза", "attack"),
        ActionDef("bbc_crowbar", "Усиленный удар монтировкой", "attack"),
        ActionDef("bbc_excuse", "Excuse Me Sir", "scorched"),
        ActionDef("bbc_aura", "Aura Farming", "absorb"),
    ],
    "mimic": [
        ActionDef("mm_random", "Случайный удар", "attack"),
        ActionDef("mm_copy1", "Копирование 1", "copy"),
        ActionDef("mm_copy2", "Копирование 2", "copy"),
        ActionDef("mm_reroll", "Смена способностей", "copy_reroll"),
        ActionDef("mm_dodge", "Случайный уворот", "dodge"),
    ],
    "black_noir": [
        ActionDef("bn_mighty", "Мощнейший удар", "attack"),
        ActionDef("bn_knife", "Бросок ножа", "attack_multi"),
        ActionDef("bn_regen_dodge", "Регенеративный уворот", "dodge"),
        ActionDef("bn_friends", "Ради друзей", "buff"),
        ActionDef("bn_stolen_shot", "Украденный выстрел", "attack_ult"),
    ],
    "flying_noir": [
        ActionDef("fn_punch", "Усиленный удар", "attack"),
        ActionDef("fn_katana", "Тяжёлый удар Катаной", "attack"),
        ActionDef("fn_actor", "Хороший актёр", "buff"),
        ActionDef("fn_bulletproof", "Пуленепробиваемый", "once_battle"),
    ],
}


def get_actions_for_character(character: str) -> list[ActionDef]:
    if character in ACTIONS:
        return ACTIONS[character]
    return ACTIONS["loh"]


def character_has_native_escape(character: str) -> bool:
    """Персонаж уже имеет свою способность побега (не общую кнопку)."""
    return any(
        act.kind in ("escape", "escape_sb")
        for act in get_actions_for_character(character)
    )


def get_action_label(action_id: str) -> str:
    for acts in ACTIONS.values():
        for act in acts:
            if act.id == action_id:
                return act.label
    extra = {
        "item_virus": "Вирус",
        "surrender": "Сдача",
        "battle_escape": "Побег",
        "beam_dodge": "Уворот от луча",
        "beam_counter": "Контратака на луч",
        "hl_scorched": "Выжженная земля",
    }
    return extra.get(action_id, action_id)


def action_disabled(
    action_id: str, status, character: str
) -> bool:  # noqa: ANN001
    if action_id == "mm_copy1" and not getattr(status, "mimic_copy_1", ""):
        return True
    if action_id == "mm_copy2" and not getattr(status, "mimic_copy_2", ""):
        return True
    if character == "mimic":
        from game.battle_mimic import mimic_effective_action_id

        action_id = mimic_effective_action_id(action_id, status, character)
    disabled = set(status.anti_v_disabled)
    if action_id in disabled:
        return True
    if action_id == "hl_scorched" and status.scorched_pct >= 100:
        return False
    if action_id == "bbc_excuse" and status.excuse_pct >= 100:
        return False
    if action_id == "sl_heavy" and status.star_charged_pct >= 100:
        return False
    if action_id == "bu_rush" and status.rush_pct >= 100:
        return False
    if action_id == "sf_storm" and status.storm_pct >= 100:
        return False
    if action_id == "sb_beam" and status.soldier_beam_pct >= 100:
        return False
    if action_id == "bn_stolen_shot" and status.noir_stolen_used:
        return True
    if action_id == "fn_bulletproof" and status.fn_bp_used:
        return True
    cd = status.cooldowns.get(action_id, 0)
    if cd > 0:
        return True
    if action_id == "sb_beam_fire" and status.soldier_beam_pct < 100:
        return True
    if action_id == "sb_beam_charge" and status.soldier_beam_pct < 100:
        return True
    if action_id == "nm_head_explode" and status.newman_tear_pct < 100:
        return True
    if status.dodge_forbidden_turns > 0 and _is_dodge_action(
        action_id, character, status
    ):
        return True
    return False


def battle_action_label(action_id: str, label: str, status) -> str:  # noqa: ANN001
    """Подпись кнопки в бою (динамика накопления)."""
    if action_id == "mm_copy1":
        cid = getattr(status, "mimic_copy_1", "") or ""
        if cid:
            return battle_action_label(cid, get_action_label(cid), status)
        return "Копирование 1"
    if action_id == "mm_copy2":
        cid = getattr(status, "mimic_copy_2", "") or ""
        if cid:
            return battle_action_label(cid, get_action_label(cid), status)
        return "Копирование 2"
    if action_id == "hl_scorched":
        if status.scorched_pct >= 100:
            return "(100%) Выжженная земля: выпустить"
        if status.scorched_pct > 0:
            return f"({status.scorched_pct}%) Выжженная земля"
        return "Выжженная земля"
    if action_id == "bbc_excuse":
        if status.excuse_pct >= 100:
            return "(100%) Excuse Me Sir: выпустить"
        if status.excuse_pct > 0:
            return f"({status.excuse_pct}%) Excuse Me Sir"
        return "Excuse Me Sir"
    if action_id == "sl_heavy":
        if status.star_charged_pct >= 100:
            return "(100%) Тяжёлый заряженный удар: выпустить"
        if status.star_charged_pct > 0:
            return f"({status.star_charged_pct}%) Тяжёлый заряженный удар"
        return "Тяжёлый заряженный удар"
    if action_id == "sb_beam_charge" and status.soldier_beam_pct > 0:
        return f"({status.soldier_beam_pct}%) Луч: накопить"
    if action_id == "sb_beam":
        if status.soldier_beam_pct >= 100:
            return "(100%) Лучевой удар: выпустить"
        if status.soldier_beam_pct > 0:
            return f"({status.soldier_beam_pct}%) Лучевой удар"
        return "Лучевой удар"
    if action_id == "sb_beam_fire":
        if status.soldier_beam_pct >= 100:
            return "(100%) Выпустить луч"
        if status.soldier_beam_pct > 0:
            return f"({status.soldier_beam_pct}%) Выпустить луч"
    if action_id == "sf_storm_charge" and status.storm_pct > 0:
        return f"({status.storm_pct}%) Буря"
    if action_id == "sf_storm":
        if status.storm_pct >= 100:
            return "(100%) Буря: выпустить"
        if status.storm_pct > 0:
            return f"({status.storm_pct}%) Буря"
        return "Буря"
    if action_id == "sf_storm_fire":
        if status.storm_pct >= 100:
            return "(100%) Буря: выпустить"
        if status.storm_pct > 0:
            return f"({status.storm_pct}%) Буря: выпустить"
    if action_id == "nm_tear" and status.newman_tear_pct > 0:
        return f"({status.newman_tear_pct}%) Разрыв конечностей"
    if action_id == "bu_rush":
        if status.rush_pct >= 100:
            return "(100%) Разрушительный рывок: выпустить"
        if status.rush_pct > 0:
            return f"({status.rush_pct}%) Разрушительный рывок"
        return "Разрушительный рывок"
    if action_id == "nm_head_explode":
        if status.newman_tear_pct >= 100:
            return "(100%) Взрыв головы"
        if status.newman_tear_pct > 0:
            return f"({status.newman_tear_pct}%) Взрыв головы"
    return label


def get_action_kind(action_id: str) -> str | None:
    for acts in ACTIONS.values():
        for act in acts:
            if act.id == action_id:
                return act.kind
    return None


def is_comics_action(action_id: str) -> bool:
    return action_id.startswith("bbc_")


def _action_kind(action_id: str) -> str | None:
    return get_action_kind(action_id)


def _is_dodge_action(action_id: str, character: str, status=None) -> bool:  # noqa: ANN001
    if character == "mimic" and status is not None:
        from game.battle_mimic import mimic_effective_action_id

        action_id = mimic_effective_action_id(action_id, status, character)
    return _action_kind(action_id) == "dodge"
