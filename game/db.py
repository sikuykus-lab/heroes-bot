"""SQLite-хранилище."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Any, Iterator

from game.config import DB_PATH, MAX_ACTIVE_BATTLES_PER_CHAT, MAX_OPEN_CHALLENGES_PER_CHAT
from game.models import BattleState, Player


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_db() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS players (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                coins INTEGER NOT NULL DEFAULT 0,
                active_character TEXT NOT NULL DEFAULT 'loh',
                v_tier TEXT NOT NULL DEFAULT 'none',
                v24_battles_left INTEGER NOT NULL DEFAULT 0,
                v24_last_free_at REAL,
                virus_count INTEGER NOT NULL DEFAULT 0,
                anti_v_count INTEGER NOT NULL DEFAULT 0,
                display_name TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS open_challenges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                challenger_id INTEGER NOT NULL,
                target_id INTEGER,
                message_id INTEGER,
                created_at REAL NOT NULL,
                expires_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                p1_id INTEGER NOT NULL,
                p2_id INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_loh_confirm (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                challenge_id INTEGER NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS promo_redemptions (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                code TEXT NOT NULL,
                redeemed_at REAL NOT NULL,
                PRIMARY KEY (chat_id, user_id, code)
            );

            CREATE TABLE IF NOT EXISTS chat_bot_admins (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                granted_by INTEGER,
                granted_at REAL NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS chat_bot_staff (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                granted_by INTEGER,
                granted_at REAL NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS chat_bot_senior_staff (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                granted_by INTEGER,
                granted_at REAL NOT NULL,
                PRIMARY KEY (chat_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS player_achievements (
                chat_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at REAL NOT NULL,
                PRIMARY KEY (chat_id, user_id, achievement_id)
            );

            CREATE TABLE IF NOT EXISTS chat_achievement_defs (
                chat_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                title TEXT NOT NULL,
                criteria TEXT NOT NULL,
                exclusive INTEGER NOT NULL DEFAULT 0,
                emoji TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL,
                PRIMARY KEY (chat_id, achievement_id)
            );

            CREATE TABLE IF NOT EXISTS chat_shop_blocks (
                chat_id INTEGER NOT NULL,
                item_id TEXT NOT NULL,
                blocked_at REAL NOT NULL,
                PRIMARY KEY (chat_id, item_id)
            );

            CREATE TABLE IF NOT EXISTS chat_currency (
                chat_id INTEGER PRIMARY KEY,
                currency TEXT NOT NULL DEFAULT 'vcoins'
            );

            CREATE TABLE IF NOT EXISTS chat_challenge_limit (
                chat_id INTEGER PRIMARY KEY,
                max_open INTEGER NOT NULL DEFAULT 3
            );

            CREATE TABLE IF NOT EXISTS chat_battle_limit (
                chat_id INTEGER PRIMARY KEY,
                max_active INTEGER NOT NULL DEFAULT 3
            );

            CREATE TABLE IF NOT EXISTS chat_cheats (
                chat_id INTEGER PRIMARY KEY,
                enabled INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS chat_welcome_sent (
                chat_id INTEGER PRIMARY KEY,
                sent_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS bot_group_chats (
                chat_id INTEGER PRIMARY KEY,
                added_at REAL NOT NULL
            );
            """
        )
        _migrate_battles_table(conn)
        _migrate_players_username(conn)
        _migrate_players_wins(conn)
        _migrate_players_losses(conn)
        _migrate_ability_slots(conn)
        _migrate_open_challenges_table(conn)
        _migrate_bot_group_chats(conn)


def get_chat_currency(chat_id: int) -> str:
    from game.currency import CURRENCY_VCOINS

    with get_db() as conn:
        row = conn.execute(
            "SELECT currency FROM chat_currency WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    if not row:
        return CURRENCY_VCOINS
    cur = str(row["currency"] or CURRENCY_VCOINS)
    if cur not in ("vcoins", "rubles"):
        return CURRENCY_VCOINS
    return cur


def set_chat_currency(chat_id: int, currency: str) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_currency (chat_id, currency)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET currency = excluded.currency
            """,
            (chat_id, currency),
        )


def get_max_open_challenges(chat_id: int) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT max_open FROM chat_challenge_limit WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    if not row:
        return MAX_OPEN_CHALLENGES_PER_CHAT
    return max(1, int(row["max_open"]))


def set_max_open_challenges(chat_id: int, max_open: int) -> None:
    limit = max(1, int(max_open))
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_challenge_limit (chat_id, max_open)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET max_open = excluded.max_open
            """,
            (chat_id, limit),
        )


def get_max_active_battles(chat_id: int) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT max_active FROM chat_battle_limit WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    if not row:
        return MAX_ACTIVE_BATTLES_PER_CHAT
    return max(1, int(row["max_active"]))


def set_max_active_battles(chat_id: int, max_active: int) -> None:
    limit = max(1, int(max_active))
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_battle_limit (chat_id, max_active)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET max_active = excluded.max_active
            """,
            (chat_id, limit),
        )


def get_chat_cheats_enabled(chat_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT enabled FROM chat_cheats WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return bool(row and row["enabled"])


def set_chat_cheats_enabled(chat_id: int, enabled: bool) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_cheats (chat_id, enabled)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET enabled = excluded.enabled
            """,
            (chat_id, 1 if enabled else 0),
        )


def chat_welcome_was_sent(chat_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            "SELECT 1 FROM chat_welcome_sent WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
    return row is not None


def mark_chat_welcome_sent(chat_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_welcome_sent (chat_id, sent_at)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO NOTHING
            """,
            (chat_id, time.time()),
        )


def register_bot_group(chat_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO bot_group_chats (chat_id, added_at)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO NOTHING
            """,
            (chat_id, time.time()),
        )


def unregister_bot_group(chat_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM bot_group_chats WHERE chat_id = ?", (chat_id,))


def list_bot_group_chats() -> list[int]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT chat_id FROM bot_group_chats ORDER BY chat_id"
        ).fetchall()
    return [int(row["chat_id"]) for row in rows]


def _migrate_bot_group_chats(conn: sqlite3.Connection) -> None:
    """Заполняет список групп из уже известных chat_id."""
    sources = (
        "SELECT DISTINCT chat_id FROM players",
        "SELECT DISTINCT chat_id FROM battles",
        "SELECT DISTINCT chat_id FROM open_challenges",
        "SELECT DISTINCT chat_id FROM chat_bot_admins",
    )
    chat_ids: set[int] = set()
    for query in sources:
        try:
            for row in conn.execute(query):
                chat_ids.add(int(row["chat_id"]))
        except sqlite3.OperationalError:
            continue
    now = time.time()
    for chat_id in chat_ids:
        conn.execute(
            """
            INSERT INTO bot_group_chats (chat_id, added_at)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO NOTHING
            """,
            (chat_id, now),
        )


def _migrate_players_wins(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "wins" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN wins INTEGER NOT NULL DEFAULT 0"
        )


def _migrate_ability_slots(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "ability_slots_unlocked" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN ability_slots_unlocked INTEGER NOT NULL DEFAULT 1"
        )
    if "selected_ability_slot" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN selected_ability_slot INTEGER NOT NULL DEFAULT 1"
        )
    if "owned_abilities_json" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN owned_abilities_json TEXT NOT NULL DEFAULT '[]'"
        )
    if "equipped_abilities_json" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN equipped_abilities_json TEXT NOT NULL DEFAULT '[]'"
        )


def _migrate_players_losses(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "losses" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN losses INTEGER NOT NULL DEFAULT 0"
        )


def _migrate_players_username(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(players)").fetchall()}
    if "telegram_username" not in cols:
        conn.execute(
            "ALTER TABLE players ADD COLUMN telegram_username TEXT NOT NULL DEFAULT ''"
        )


def _migrate_open_challenges_table(conn: sqlite3.Connection) -> None:
    """Убирает UNIQUE(chat_id) у open_challenges для нескольких вызовов в чате."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='open_challenges'"
    ).fetchone()
    if not row or "UNIQUE" not in (row[0] or ""):
        return
    conn.executescript(
        """
        CREATE TABLE open_challenges_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            challenger_id INTEGER NOT NULL,
            target_id INTEGER,
            message_id INTEGER,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL
        );
        INSERT INTO open_challenges_new SELECT * FROM open_challenges;
        DROP TABLE open_challenges;
        ALTER TABLE open_challenges_new RENAME TO open_challenges;
        """
    )


def _migrate_battles_table(conn: sqlite3.Connection) -> None:
    """Убирает UNIQUE(chat_id) у battles для нескольких боёв в чате."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='battles'"
    ).fetchone()
    if not row or "UNIQUE" not in (row[0] or ""):
        return
    conn.executescript(
        """
        CREATE TABLE battles_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            p1_id INTEGER NOT NULL,
            p2_id INTEGER NOT NULL,
            state_json TEXT NOT NULL,
            created_at REAL NOT NULL
        );
        INSERT INTO battles_new SELECT * FROM battles;
        DROP TABLE battles;
        ALTER TABLE battles_new RENAME TO battles;
        """
    )


def _row_to_player(row: sqlite3.Row) -> Player:
    return Player(
        chat_id=row["chat_id"],
        user_id=row["user_id"],
        coins=row["coins"],
        active_character=row["active_character"],
        v_tier=row["v_tier"],
        v24_battles_left=row["v24_battles_left"],
        v24_last_free_at=row["v24_last_free_at"],
        virus_count=row["virus_count"],
        anti_v_count=row["anti_v_count"],
        display_name=row["display_name"] or "",
        telegram_username=(row["telegram_username"] or "")
        if "telegram_username" in row.keys()
        else "",
        wins=int(row["wins"] or 0) if "wins" in row.keys() else 0,
        losses=int(row["losses"] or 0) if "losses" in row.keys() else 0,
        ability_slots_unlocked=int(row["ability_slots_unlocked"] or 1)
        if "ability_slots_unlocked" in row.keys()
        else 1,
        selected_ability_slot=int(row["selected_ability_slot"] or 1)
        if "selected_ability_slot" in row.keys()
        else 1,
        owned_abilities_json=row["owned_abilities_json"] or "[]"
        if "owned_abilities_json" in row.keys()
        else "[]",
        equipped_abilities_json=row["equipped_abilities_json"] or "[]"
        if "equipped_abilities_json" in row.keys()
        else "[]",
    )


def top_players_by_wins(chat_id: int, limit: int = 15) -> list[Player]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM players
            WHERE chat_id = ?
            ORDER BY wins DESC, coins DESC, user_id ASC
            LIMIT ?
            """,
            (chat_id, limit),
        ).fetchall()
    return [_row_to_player(row) for row in rows]


def list_players_in_chat(chat_id: int) -> list[Player]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM players WHERE chat_id = ? ORDER BY user_id",
            (chat_id,),
        ).fetchall()
    return [_row_to_player(row) for row in rows]


def find_player_by_username(chat_id: int, username: str) -> Player | None:
    uname = username.lstrip("@").lower()
    if not uname:
        return None
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM players
            WHERE chat_id = ? AND LOWER(telegram_username) = ?
            """,
            (chat_id, uname),
        ).fetchone()
    return _row_to_player(row) if row else None


def get_or_create_player(
    chat_id: int,
    user_id: int,
    display_name: str = "",
    telegram_username: str = "",
) -> Player:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM players WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        ).fetchone()
        if row:
            uname = (telegram_username or "").lstrip("@")
            if display_name and display_name != row["display_name"]:
                conn.execute(
                    "UPDATE players SET display_name = ? WHERE chat_id = ? AND user_id = ?",
                    (display_name, chat_id, user_id),
                )
            if uname and uname.lower() != (row["telegram_username"] or "").lower():
                conn.execute(
                    """
                    UPDATE players SET telegram_username = ?
                    WHERE chat_id = ? AND user_id = ?
                    """,
                    (uname, chat_id, user_id),
                )
            row = conn.execute(
                "SELECT * FROM players WHERE chat_id = ? AND user_id = ?",
                (chat_id, user_id),
            ).fetchone()
            player = _row_to_player(row)
            from game.characters import apply_super_promotion

            before = player.active_character
            apply_super_promotion(player)
            if player.active_character != before:
                save_player(player)
            return player

        uname = (telegram_username or "").lstrip("@")
        conn.execute(
            """
            INSERT INTO players (chat_id, user_id, display_name, telegram_username)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user_id, display_name, uname),
        )
        row = conn.execute(
            "SELECT * FROM players WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        ).fetchone()
        return _row_to_player(row)


def save_player(player: Player) -> None:
    with get_db() as conn:
        conn.execute(
            """
            UPDATE players SET
                coins = ?,
                active_character = ?,
                v_tier = ?,
                v24_battles_left = ?,
                v24_last_free_at = ?,
                virus_count = ?,
                anti_v_count = ?,
                display_name = ?,
                telegram_username = ?,
                wins = ?,
                losses = ?,
                ability_slots_unlocked = ?,
                selected_ability_slot = ?,
                owned_abilities_json = ?,
                equipped_abilities_json = ?
            WHERE chat_id = ? AND user_id = ?
            """,
            (
                player.coins,
                player.active_character,
                player.v_tier,
                player.v24_battles_left,
                player.v24_last_free_at,
                player.virus_count,
                player.anti_v_count,
                player.display_name,
                player.telegram_username,
                player.wins,
                player.losses,
                player.ability_slots_unlocked,
                player.selected_ability_slot,
                player.owned_abilities_json,
                player.equipped_abilities_json,
                player.chat_id,
                player.user_id,
            ),
        )


def count_active_battles(chat_id: int) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM battles WHERE chat_id = ?", (chat_id,)
        ).fetchone()
        return int(row["c"]) if row else 0


def battles_limit_reached(chat_id: int) -> bool:
    return count_active_battles(chat_id) >= get_max_active_battles(chat_id)


def get_battle_by_id(
    battle_id: int,
) -> tuple[int, int, int, int, BattleState] | None:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM battles WHERE id = ?", (battle_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["state_json"])
        state = BattleState.from_dict(
            row["id"], row["chat_id"], row["p1_id"], row["p2_id"], data
        )
        state.battle_id = row["id"]
        return row["id"], row["chat_id"], row["p1_id"], row["p2_id"], state


def get_active_battle(chat_id: int) -> tuple[int, int, int, BattleState] | None:
    """Первый активный бой в чате (legacy)."""
    battles = list_active_battles(chat_id)
    if not battles:
        return None
    battle_id, p1_id, p2_id, state = battles[0]
    return battle_id, p1_id, p2_id, state


def list_active_battles(
    chat_id: int,
) -> list[tuple[int, int, int, BattleState]]:
    """Все активные бои в чате: (battle_id, p1_id, p2_id, state)."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM battles WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        ).fetchall()
    out: list[tuple[int, int, int, BattleState]] = []
    for row in rows:
        data = json.loads(row["state_json"])
        state = BattleState.from_dict(
            row["id"], row["chat_id"], row["p1_id"], row["p2_id"], data
        )
        state.battle_id = row["id"]
        out.append((row["id"], row["p1_id"], row["p2_id"], state))
    return out


def save_battle(
    battle_id: int, chat_id: int, p1_id: int, p2_id: int, state: BattleState
) -> None:
    with get_db() as conn:
        conn.execute(
            """
            UPDATE battles SET state_json = ? WHERE id = ?
            """,
            (json.dumps(state.to_dict(), ensure_ascii=False), battle_id),
        )


def create_battle(chat_id: int, p1_id: int, p2_id: int, state: BattleState) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO battles (chat_id, p1_id, p2_id, state_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                p1_id,
                p2_id,
                json.dumps(state.to_dict(), ensure_ascii=False),
                time.time(),
            ),
        )
        return int(cur.lastrowid)


def delete_battle_by_id(battle_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM battles WHERE id = ?", (battle_id,))


def delete_battle(chat_id: int) -> None:
    """Удаляет все бои в чате (legacy)."""
    with get_db() as conn:
        conn.execute("DELETE FROM battles WHERE chat_id = ?", (chat_id,))


def create_challenge(
    chat_id: int,
    challenger_id: int,
    target_id: int | None,
    message_id: int,
    expires_at: float,
) -> int:
    with get_db() as conn:
        cur = conn.execute(
            """
            INSERT INTO open_challenges
            (chat_id, challenger_id, target_id, message_id, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (chat_id, challenger_id, target_id, message_id, time.time(), expires_at),
        )
        return int(cur.lastrowid)


def count_open_challenges(chat_id: int) -> int:
    with get_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM open_challenges WHERE chat_id = ?",
            (chat_id,),
        ).fetchone()
        return int(row["c"] or 0)


def challenges_limit_reached(chat_id: int) -> bool:
    return count_open_challenges(chat_id) >= get_max_open_challenges(chat_id)


def get_challenge_by_id(challenge_id: int) -> dict[str, Any] | None:
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM open_challenges WHERE id = ?", (challenge_id,)
        ).fetchone()
        if not row:
            return None
        return dict(row)


def list_open_challenges(chat_id: int) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM open_challenges WHERE chat_id = ? ORDER BY id",
            (chat_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_challenge(chat_id: int) -> dict[str, Any] | None:
    """Первый открытый вызов в чате (legacy)."""
    challenges = list_open_challenges(chat_id)
    return challenges[0] if challenges else None


def delete_challenge_by_id(challenge_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM open_challenges WHERE id = ?", (challenge_id,))


def delete_challenge(chat_id: int) -> None:
    with get_db() as conn:
        conn.execute("DELETE FROM open_challenges WHERE chat_id = ?", (chat_id,))


def clear_pending_loh_for_challenge(challenge_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "DELETE FROM pending_loh_confirm WHERE challenge_id = ?",
            (challenge_id,),
        )


def clear_pending_loh_for_chat(chat_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            "DELETE FROM pending_loh_confirm WHERE chat_id = ?", (chat_id,)
        )


def set_pending_loh(chat_id: int, user_id: int, challenge_id: int) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO pending_loh_confirm (chat_id, user_id, challenge_id)
            VALUES (?, ?, ?)
            """,
            (chat_id, user_id, challenge_id),
        )


def pop_pending_loh(chat_id: int, user_id: int) -> int | None:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT challenge_id FROM pending_loh_confirm
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        ).fetchone()
        if not row:
            return None
        conn.execute(
            "DELETE FROM pending_loh_confirm WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        return int(row["challenge_id"])


def promo_already_used(chat_id: int, user_id: int, code: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM promo_redemptions
            WHERE chat_id = ? AND user_id = ? AND code = ?
            """,
            (chat_id, user_id, code),
        ).fetchone()
        return row is not None


def mark_promo_used(chat_id: int, user_id: int, code: str) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO promo_redemptions (chat_id, user_id, code, redeemed_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user_id, code, time.time()),
        )


def add_bot_admin(chat_id: int, user_id: int, granted_by: int) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chat_bot_admins
            (chat_id, user_id, granted_by, granted_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user_id, granted_by, time.time()),
        )


def is_bot_admin_in_db(chat_id: int, user_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM chat_bot_admins
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        ).fetchone()
        return row is not None


def has_active_battle(chat_id: int) -> bool:
    return count_active_battles(chat_id) > 0


def user_ids_in_active_battles(chat_id: int) -> set[int]:
    ids: set[int] = set()
    for _bid, p1_id, p2_id, _state in list_active_battles(chat_id):
        ids.add(p1_id)
        ids.add(p2_id)
    return ids


def find_battle_by_message_id(
    chat_id: int, message_id: int
) -> tuple[int, int, int, BattleState] | None:
    for battle_id, p1_id, p2_id, state in list_active_battles(chat_id):
        if state.message_id == message_id:
            return battle_id, p1_id, p2_id, state
    return None


def list_all_active_battles() -> list[tuple[int, int, int, int, BattleState]]:
    """(battle_id, chat_id, p1_id, p2_id, state) по всем чатам."""
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM battles ORDER BY id").fetchall()
    out: list[tuple[int, int, int, int, BattleState]] = []
    for row in rows:
        data = json.loads(row["state_json"])
        state = BattleState.from_dict(
            row["id"], row["chat_id"], row["p1_id"], row["p2_id"], data
        )
        state.battle_id = row["id"]
        out.append((row["id"], row["chat_id"], row["p1_id"], row["p2_id"], state))
    return out


def add_bot_staff(chat_id: int, user_id: int, granted_by: int) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chat_bot_staff
            (chat_id, user_id, granted_by, granted_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user_id, granted_by, time.time()),
        )


def is_bot_staff_in_db(chat_id: int, user_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM chat_bot_staff
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        ).fetchone()
        return row is not None


def is_bot_senior_staff_in_db(chat_id: int, user_id: int) -> bool:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM chat_bot_senior_staff
            WHERE chat_id = ? AND user_id = ?
            """,
            (chat_id, user_id),
        ).fetchone()
        return row is not None


def add_bot_senior_staff(chat_id: int, user_id: int, granted_by: int) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO chat_bot_senior_staff
            (chat_id, user_id, granted_by, granted_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user_id, granted_by, time.time()),
        )


def remove_bot_staff(chat_id: int, user_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM chat_bot_staff WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        return cur.rowcount > 0


def remove_bot_senior_staff(chat_id: int, user_id: int) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            "DELETE FROM chat_bot_senior_staff WHERE chat_id = ? AND user_id = ?",
            (chat_id, user_id),
        )
        return cur.rowcount > 0


def remove_bot_staff_roles(chat_id: int, user_id: int) -> tuple[bool, bool]:
    """Снять staff и senior staff. Возвращает (был staff, был senior)."""
    was_staff = remove_bot_staff(chat_id, user_id)
    was_senior = remove_bot_senior_staff(chat_id, user_id)
    return was_staff, was_senior


def grant_achievement(chat_id: int, user_id: int, achievement_id: str) -> bool:
    """Выдать достижение. False если уже было."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM player_achievements
            WHERE chat_id = ? AND user_id = ? AND achievement_id = ?
            """,
            (chat_id, user_id, achievement_id),
        ).fetchone()
        if row:
            return False
        conn.execute(
            """
            INSERT INTO player_achievements
            (chat_id, user_id, achievement_id, unlocked_at)
            VALUES (?, ?, ?, ?)
            """,
            (chat_id, user_id, achievement_id, time.time()),
        )
        return True


def revoke_achievement(chat_id: int, user_id: int, achievement_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            """
            DELETE FROM player_achievements
            WHERE chat_id = ? AND user_id = ? AND achievement_id = ?
            """,
            (chat_id, user_id, achievement_id),
        )
        return cur.rowcount > 0


def has_achievement(chat_id: int, user_id: int, achievement_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM player_achievements
            WHERE chat_id = ? AND user_id = ? AND achievement_id = ?
            """,
            (chat_id, user_id, achievement_id),
        ).fetchone()
        return row is not None


def list_player_achievements(chat_id: int, user_id: int) -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT achievement_id FROM player_achievements
            WHERE chat_id = ? AND user_id = ?
            ORDER BY unlocked_at, achievement_id
            """,
            (chat_id, user_id),
        ).fetchall()
        return [str(r["achievement_id"]) for r in rows]


def _row_to_achievement_def(row: sqlite3.Row):
    from game.achievements import AchievementDef

    return AchievementDef(
        id=row["achievement_id"],
        title=row["title"],
        criteria=row["criteria"],
        exclusive=bool(row["exclusive"]),
        emoji=row["emoji"] or "",
        admin_only=True,
    )


def create_chat_achievement_def(
    chat_id: int,
    achievement_id: str,
    title: str,
    criteria: str,
    *,
    exclusive: bool = False,
    emoji: str = "",
) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO chat_achievement_defs
            (chat_id, achievement_id, title, criteria, exclusive, emoji, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                achievement_id,
                title,
                criteria,
                int(exclusive),
                emoji,
                time.time(),
            ),
        )


def delete_chat_achievement_def(chat_id: int, achievement_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            """
            DELETE FROM chat_achievement_defs
            WHERE chat_id = ? AND achievement_id = ?
            """,
            (chat_id, achievement_id),
        )
        if cur.rowcount <= 0:
            return False
        conn.execute(
            """
            DELETE FROM player_achievements
            WHERE chat_id = ? AND achievement_id = ?
            """,
            (chat_id, achievement_id),
        )
        return True


def get_chat_achievement_def(chat_id: int, achievement_id: str):
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT * FROM chat_achievement_defs
            WHERE chat_id = ? AND achievement_id = ?
            """,
            (chat_id, achievement_id),
        ).fetchone()
        if not row:
            return None
        return _row_to_achievement_def(row)


def list_chat_achievement_defs(chat_id: int) -> list:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT * FROM chat_achievement_defs
            WHERE chat_id = ?
            ORDER BY created_at, achievement_id
            """,
            (chat_id,),
        ).fetchall()
        return [_row_to_achievement_def(r) for r in rows]


def is_custom_achievement_id(achievement_id: str) -> bool:
    return achievement_id.startswith("custom_")


def block_shop_item(chat_id: int, item_id: str) -> bool:
    """Заблокировать товар. False если уже заблокирован."""
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM chat_shop_blocks
            WHERE chat_id = ? AND item_id = ?
            """,
            (chat_id, item_id),
        ).fetchone()
        if row:
            return False
        conn.execute(
            """
            INSERT INTO chat_shop_blocks (chat_id, item_id, blocked_at)
            VALUES (?, ?, ?)
            """,
            (chat_id, item_id, time.time()),
        )
        return True


def unblock_shop_item(chat_id: int, item_id: str) -> bool:
    with get_db() as conn:
        cur = conn.execute(
            """
            DELETE FROM chat_shop_blocks
            WHERE chat_id = ? AND item_id = ?
            """,
            (chat_id, item_id),
        )
        return cur.rowcount > 0


def is_shop_item_blocked(chat_id: int, item_id: str) -> bool:
    with get_db() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM chat_shop_blocks
            WHERE chat_id = ? AND item_id = ?
            """,
            (chat_id, item_id),
        ).fetchone()
        return row is not None


def list_blocked_shop_items(chat_id: int) -> list[str]:
    with get_db() as conn:
        rows = conn.execute(
            """
            SELECT item_id FROM chat_shop_blocks
            WHERE chat_id = ?
            ORDER BY blocked_at, item_id
            """,
            (chat_id,),
        ).fetchall()
        return [str(r["item_id"]) for r in rows]
