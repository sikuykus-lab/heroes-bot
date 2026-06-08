"""Модели данных."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Player:
    chat_id: int
    user_id: int
    coins: int = 0
    active_character: str = "loh"
    v_tier: str = "none"
    v24_battles_left: int = 0
    v24_last_free_at: float | None = None
    virus_count: int = 0
    anti_v_count: int = 0
    display_name: str = ""
    telegram_username: str = ""
    wins: int = 0
    losses: int = 0
    ability_slots_unlocked: int = 1
    selected_ability_slot: int = 1
    owned_abilities_json: str = "[]"
    equipped_abilities_json: str = "[]"


@dataclass
class PlayerBattleStatus:
    cooldowns: dict[str, int] = field(default_factory=dict)
    soldier_beam_pct: int = 0
    storm_pct: int = 0
    blind_turns: int = 0
    miss_chance: float = 0.0
    stunned: int = 0
    skip_next: bool = False
    absorb_pct: int = 0
    dodge_active: bool = False
    dodge_hidden_pending: bool = False
    dodge_hidden_lines: list[str] = field(default_factory=list)
    anti_v_disabled: list[str] = field(default_factory=list)
    newman_tear_pct: int = 0
    scorched_pct: int = 0
    excuse_pct: int = 0
    star_charged_pct: int = 0
    dodge_forbidden_turns: int = 0
    ability_block_turns: int = 0
    damage_dealt_mult: float = 1.0
    damage_taken_mult: float = 1.0
    dealt_mult_turns: int = 0
    taken_mult_turns: int = 0
    mimic_copy_1: str = ""
    mimic_copy_2: str = ""
    rush_pct: int = 0
    noir_stolen_used: bool = False
    noir_bulletproof_turns: int = 0
    noir_punch_buff: float = 1.0
    noir_punch_buff_turns: int = 0
    noir_actor_dodge: bool = False
    aim_impaired_turns: int = 0
    aim_impaired_miss: float = 0.0
    fn_bp_used: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "cooldowns": dict(self.cooldowns),
            "soldier_beam_pct": self.soldier_beam_pct,
            "storm_pct": self.storm_pct,
            "blind_turns": self.blind_turns,
            "miss_chance": self.miss_chance,
            "stunned": self.stunned,
            "skip_next": self.skip_next,
            "absorb_pct": self.absorb_pct,
            "dodge_active": self.dodge_active,
            "dodge_hidden_pending": self.dodge_hidden_pending,
            "dodge_hidden_lines": list(self.dodge_hidden_lines),
            "anti_v_disabled": list(self.anti_v_disabled),
            "newman_tear_pct": self.newman_tear_pct,
            "scorched_pct": self.scorched_pct,
            "excuse_pct": self.excuse_pct,
            "star_charged_pct": self.star_charged_pct,
            "dodge_forbidden_turns": self.dodge_forbidden_turns,
            "ability_block_turns": self.ability_block_turns,
            "damage_dealt_mult": self.damage_dealt_mult,
            "damage_taken_mult": self.damage_taken_mult,
            "dealt_mult_turns": self.dealt_mult_turns,
            "taken_mult_turns": self.taken_mult_turns,
            "mimic_copy_1": self.mimic_copy_1,
            "mimic_copy_2": self.mimic_copy_2,
            "rush_pct": self.rush_pct,
            "noir_stolen_used": self.noir_stolen_used,
            "noir_bulletproof_turns": self.noir_bulletproof_turns,
            "noir_punch_buff": self.noir_punch_buff,
            "noir_punch_buff_turns": self.noir_punch_buff_turns,
            "noir_actor_dodge": self.noir_actor_dodge,
            "aim_impaired_turns": self.aim_impaired_turns,
            "aim_impaired_miss": self.aim_impaired_miss,
            "fn_bp_used": self.fn_bp_used,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> PlayerBattleStatus:
        if not data:
            return cls()
        return cls(
            cooldowns=dict(data.get("cooldowns") or {}),
            soldier_beam_pct=int(data.get("soldier_beam_pct") or 0),
            storm_pct=int(data.get("storm_pct") or 0),
            blind_turns=int(data.get("blind_turns") or 0),
            miss_chance=float(data.get("miss_chance") or 0),
            stunned=int(data.get("stunned") or 0),
            skip_next=bool(data.get("skip_next")),
            absorb_pct=int(data.get("absorb_pct") or 0),
            dodge_active=bool(data.get("dodge_active")),
            dodge_hidden_pending=bool(data.get("dodge_hidden_pending")),
            dodge_hidden_lines=list(data.get("dodge_hidden_lines") or []),
            anti_v_disabled=list(data.get("anti_v_disabled") or []),
            newman_tear_pct=int(data.get("newman_tear_pct") or 0),
            scorched_pct=int(data.get("scorched_pct") or 0),
            excuse_pct=int(data.get("excuse_pct") or 0),
            star_charged_pct=int(data.get("star_charged_pct") or 0),
            dodge_forbidden_turns=int(data.get("dodge_forbidden_turns") or 0),
            ability_block_turns=int(data.get("ability_block_turns") or 0),
            damage_dealt_mult=float(data.get("damage_dealt_mult") or 1.0),
            damage_taken_mult=float(data.get("damage_taken_mult") or 1.0),
            dealt_mult_turns=int(data.get("dealt_mult_turns") or 0),
            taken_mult_turns=int(data.get("taken_mult_turns") or 0),
            mimic_copy_1=str(data.get("mimic_copy_1") or ""),
            mimic_copy_2=str(data.get("mimic_copy_2") or ""),
            rush_pct=int(data.get("rush_pct") or 0),
            noir_stolen_used=bool(data.get("noir_stolen_used")),
            noir_bulletproof_turns=int(data.get("noir_bulletproof_turns") or 0),
            noir_punch_buff=float(data.get("noir_punch_buff") or 1.0),
            noir_punch_buff_turns=int(data.get("noir_punch_buff_turns") or 0),
            noir_actor_dodge=bool(data.get("noir_actor_dodge")),
            aim_impaired_turns=int(data.get("aim_impaired_turns") or 0),
            aim_impaired_miss=float(data.get("aim_impaired_miss") or 0.0),
            fn_bp_used=bool(data.get("fn_bp_used")),
        )


@dataclass
class BattleState:
    battle_id: int
    chat_id: int
    p1_id: int
    p2_id: int
    p1_hp: int = 100
    p2_hp: int = 100
    turn_user_id: int = 0
    p1_character: str = "loh"
    p2_character: str = "loh"
    p1_status: PlayerBattleStatus = field(default_factory=PlayerBattleStatus)
    p2_status: PlayerBattleStatus = field(default_factory=PlayerBattleStatus)
    message_id: int | None = None
    last_dice_message_id: int | None = None
    last_turn_report: dict | None = None
    beam_response_user_id: int | None = None
    beam_response_attacker_id: int | None = None
    last_activity_at: float = 0.0

    def player_side(self, user_id: int) -> str:
        return "p1" if user_id == self.p1_id else "p2"

    def hp_for(self, user_id: int) -> int:
        return self.p1_hp if user_id == self.p1_id else self.p2_hp

    def set_hp_for(self, user_id: int, hp: int) -> None:
        if user_id == self.p1_id:
            self.p1_hp = max(0, hp)
        else:
            self.p2_hp = max(0, hp)

    def status_for(self, user_id: int) -> PlayerBattleStatus:
        return self.p1_status if user_id == self.p1_id else self.p2_status

    def opponent_id(self, user_id: int) -> int:
        return self.p2_id if user_id == self.p1_id else self.p1_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "p1_hp": self.p1_hp,
            "p2_hp": self.p2_hp,
            "turn_user_id": self.turn_user_id,
            "p1_character": self.p1_character,
            "p2_character": self.p2_character,
            "p1_status": self.p1_status.to_dict(),
            "p2_status": self.p2_status.to_dict(),
            "message_id": self.message_id,
            "last_dice_message_id": self.last_dice_message_id,
            "last_turn_report": self.last_turn_report,
            "beam_response_user_id": self.beam_response_user_id,
            "beam_response_attacker_id": self.beam_response_attacker_id,
            "last_activity_at": self.last_activity_at,
        }

    @classmethod
    def from_dict(
        cls,
        battle_id: int,
        chat_id: int,
        p1_id: int,
        p2_id: int,
        data: dict[str, Any],
    ) -> BattleState:
        return cls(
            battle_id=battle_id,
            chat_id=chat_id,
            p1_id=p1_id,
            p2_id=p2_id,
            p1_hp=int(data.get("p1_hp", 100)),
            p2_hp=int(data.get("p2_hp", 100)),
            turn_user_id=int(data.get("turn_user_id", p1_id)),
            p1_character=str(data.get("p1_character", "loh")),
            p2_character=str(data.get("p2_character", "loh")),
            p1_status=PlayerBattleStatus.from_dict(data.get("p1_status")),
            p2_status=PlayerBattleStatus.from_dict(data.get("p2_status")),
            message_id=data.get("message_id"),
            last_dice_message_id=data.get("last_dice_message_id"),
            last_turn_report=data.get("last_turn_report"),
            beam_response_user_id=data.get("beam_response_user_id"),
            beam_response_attacker_id=data.get("beam_response_attacker_id"),
            last_activity_at=float(data.get("last_activity_at") or 0),
        )
