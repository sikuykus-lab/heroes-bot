"""Начисление V Coin после боя."""

from __future__ import annotations

from game import db
from game.config import REWARDS
from game.characters import counts_battle_stats
from game.models import Player


def reward_tier_key(v_tier: str) -> str:
    if v_tier in ("none", "v14bb"):
        return "none"
    if v_tier == "v24":
        return "v24"
    if v_tier == "v1":
        return "v1"
    if v_tier == "v":
        return "v"
    return "none"


def apply_battle_rewards(
    chat_id: int,
    winner_id: int,
    loser_id: int,
    winner: Player,
    loser: Player,
) -> tuple[int, int]:
    """Награда по tier соперника. Возвращает (победителю, проигравшему)."""
    win_key = reward_tier_key(loser.v_tier)
    loss_key = reward_tier_key(winner.v_tier)

    win_amt, _ = REWARDS.get(win_key, REWARDS["none"])
    _, loss_amt = REWARDS.get(loss_key, REWARDS["none"])

    winner.coins += win_amt
    loser.coins += loss_amt
    if counts_battle_stats(winner.v_tier) and counts_battle_stats(loser.v_tier):
        winner.wins += 1
        loser.losses += 1

    db.save_player(winner)
    db.save_player(loser)

    return win_amt, loss_amt


def decrement_v24_after_battle(player: Player) -> None:
    if player.v_tier != "v24":
        return
    player.v24_battles_left = max(0, player.v24_battles_left - 1)
    if player.v24_battles_left <= 0:
        player.v_tier = "none"
        player.active_character = "loh"
    db.save_player(player)
