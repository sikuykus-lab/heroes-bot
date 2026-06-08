"""Предупреждения перед принятием боя."""

from __future__ import annotations

LOH_WARNING_NONE = (
    "⚠️ Ты лох! Без V и способностей суперов.\n"
    "Рекомендуем зайти в магазин.\n"
    "Всё равно принять?"
)

LOH_WARNING_V14BB = (
    "⚠️ Помимо того что ты полнейший лох, так ты ещё и далбо*б\n\n"
    "Ты точно хочешь пойти и отсосать?"
)


def needs_fight_warning(v_tier: str) -> bool:
    return v_tier in ("none", "v14bb")


def fight_warning_text(v_tier: str) -> str:
    if v_tier == "v14bb":
        return LOH_WARNING_V14BB
    return LOH_WARNING_NONE
