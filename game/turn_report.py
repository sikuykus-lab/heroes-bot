"""Отчёт о последнем ходе для сообщения боя."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class TurnReport:
    roll: int
    action_label: str = ""
    effect_lines: list[str] = field(default_factory=list)
    damage: int | None = None
    damage_target_id: int | None = None
    extra_rolls: list[int] = field(default_factory=list)
    dodge_outcome_hidden: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "roll": self.roll,
            "action_label": self.action_label,
            "effect_lines": list(self.effect_lines),
            "damage": self.damage,
            "damage_target_id": self.damage_target_id,
            "extra_rolls": list(self.extra_rolls),
            "dodge_outcome_hidden": self.dodge_outcome_hidden,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> TurnReport | None:
        if not data:
            return None
        return cls(
            roll=int(data["roll"]),
            action_label=str(data.get("action_label") or ""),
            effect_lines=list(data.get("effect_lines") or []),
            damage=data.get("damage"),
            damage_target_id=data.get("damage_target_id"),
            extra_rolls=[int(x) for x in (data.get("extra_rolls") or [])],
            dodge_outcome_hidden=bool(data.get("dodge_outcome_hidden")),
        )
