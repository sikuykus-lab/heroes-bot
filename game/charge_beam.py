"""Внебоевой луч Солдатика (/chargebeam)."""

from __future__ import annotations

from game import db
from game.characters import admin_clear_hero


def demote_user_to_loh(chat_id: int, user_id: int) -> None:
    player = db.get_or_create_player(chat_id, user_id)
    admin_clear_hero(player)
    db.save_player(player)
    for battle_id, p1_id, p2_id, state in db.list_active_battles(chat_id):
        if user_id == p1_id:
            state.p1_character = "loh"
        elif user_id == p2_id:
            state.p2_character = "loh"
        else:
            continue
        db.save_battle(battle_id, chat_id, p1_id, p2_id, state)
