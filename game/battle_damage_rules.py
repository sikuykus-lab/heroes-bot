"""Классификация атак для пуленепробиваемого Летающего Нуара."""

from __future__ import annotations

from game.characters import get_action_label

_CHARGE_RELEASE_IDS = frozenset(
    {
        "sb_beam_fire",
        "nm_head_explode",
        "sf_storm",
        "sl_heavy",
        "bu_rush",
        "hl_scorched",
        "bbc_excuse",
    }
)


def is_punch_action(action_id: str) -> bool:
    return "удар" in get_action_label(action_id).lower()


def is_charge_release_action(action_id: str, attacker_status) -> bool:  # noqa: ARG001
    return action_id in _CHARGE_RELEASE_IDS


def bypasses_bulletproof(action_id: str, attacker_status) -> bool:  # noqa: ANN001
    return is_punch_action(action_id) or is_charge_release_action(
        action_id, attacker_status
    )
