"""Достижения игроков."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from game import db
from game.models import BattleState, Player

if TYPE_CHECKING:
    from telegram import Bot


@dataclass(frozen=True)
class AchievementDef:
    id: str
    title: str
    criteria: str
    exclusive: bool = False
    emoji: str = ""
    admin_only: bool = False


ACHIEVEMENTS: dict[str, AchievementDef] = {
    "v1_first": AchievementDef(
        "v1_first", "Старее чем сама земля", "Первый раз использовать V1"
    ),
    "win_75hp": AchievementDef(
        "win_75hp", "Да я даже не вспотел", "Выиграть матч имея больше 75 хп"
    ),
    "virus_first": AchievementDef(
        "virus_first", "Глупый жулик", "Первый раз использовать Вирус в бою"
    ),
    "virus_death_first": AchievementDef(
        "virus_death_first",
        "Не выжгли получается..",
        "Первый раз умереть от Вируса",
    ),
    "secret_v_first": AchievementDef(
        "secret_v_first",
        "Я не такой же, человек как вы",
        'Первый раз получить персонажа из категории "Secret V"',
        exclusive=True,
    ),
    "wins_50": AchievementDef(
        "wins_50", "Всё ещё впереди..", "Выиграть 50 матчей"
    ),
    "wins_100": AchievementDef(
        "wins_100", "Ну мам, это точно последняя", "Выиграть 100 матчей"
    ),
    "top1_first": AchievementDef(
        "top1_first",
        "Один такой",
        "В первый раз занять первое место в топе",
        exclusive=True,
    ),
    "top1_test_season": AchievementDef(
        "top1_test_season",
        "Top 1 Test Season",
        "Выдаётся только через команду /addach",
        exclusive=True,
        admin_only=True,
    ),
    "beam_demote_first": AchievementDef(
        "beam_demote_first",
        "Слишком много п*здел..",
        'Первый раз стать лохом из за способности "лучевой удар" персонажа Солдатик '
        "(также работает если на пользователе использовали /chargebeam вне боя)",
    ),
    "beat_secret_v": AchievementDef(
        "beat_secret_v",
        "Бро тебя понерфят.",
        "Первый раз победить Secret V персонажа",
        exclusive=True,
    ),
    "win_as_loh": AchievementDef(
        "win_as_loh",
        "А ты не лох оказывается..",
        "Первый раз выиграть кого то на персонаже Лох",
        exclusive=True,
    ),
    "v14bb_buy": AchievementDef(
        "v14bb_buy",
        "Далбоеб",
        "Первый раз купить V14BB",
        emoji="🤪",
    ),
    "main_femboy": AchievementDef(
        "main_femboy",
        "Главный фембой чата",
        "быть тупым",
        admin_only=True,
    ),
}

ACHIEVEMENT_ORDER: list[str] = list(ACHIEVEMENTS.keys())

BUILTIN_ACHIEVEMENTS = ACHIEVEMENTS


def get_achievement_order(chat_id: int) -> list[str]:
    custom_ids = [a.id for a in db.list_chat_achievement_defs(chat_id)]
    return ACHIEVEMENT_ORDER + custom_ids


def get_achievement(chat_id: int, achievement_id: str) -> AchievementDef | None:
    builtin = BUILTIN_ACHIEVEMENTS.get(achievement_id)
    if builtin:
        return builtin
    return db.get_chat_achievement_def(chat_id, achievement_id)


def create_custom_achievement(
    chat_id: int, title: str, criteria: str
) -> AchievementDef:
    import time as _time

    ach_id = f"custom_{int(_time.time())}"
    ach = AchievementDef(
        id=ach_id,
        title=title.strip(),
        criteria=criteria.strip(),
        admin_only=True,
    )
    db.create_chat_achievement_def(
        chat_id,
        ach.id,
        ach.title,
        ach.criteria,
    )
    return ach


def delete_custom_achievement(chat_id: int, achievement_id: str) -> bool:
    if not db.is_custom_achievement_id(achievement_id):
        return False
    return db.delete_chat_achievement_def(chat_id, achievement_id)


def format_achievement_line(ach: AchievementDef) -> str:
    return f"{display_achievement_title(ach)} [{ach.criteria}]"


def display_achievement_title(ach: AchievementDef) -> str:
    if ach.emoji:
        return f"{ach.emoji} {ach.title}"
    if ach.exclusive:
        return f"⚡ {ach.title}"
    return ach.title


def unlock_announcement(display_name: str, ach: AchievementDef) -> str:
    return (
        f"Игрок {display_name} получает достижение "
        f"{display_achievement_title(ach)}, поздравляем!"
    )


async def announce_unlock(
    bot: Bot, chat_id: int, user_id: int, ach: AchievementDef
) -> None:
    player = db.get_or_create_player(chat_id, user_id)
    name = player.display_name or "Игрок"
    await bot.send_message(chat_id=chat_id, text=unlock_announcement(name, ach))


async def announce_unlocks(
    bot: Bot, chat_id: int, user_id: int, unlocks: list[AchievementDef]
) -> None:
    for ach in unlocks:
        await announce_unlock(bot, chat_id, user_id, ach)


def format_achievements_block(chat_id: int, user_id: int) -> str:
    unlocked = set(db.list_player_achievements(chat_id, user_id))
    lines = ["[⭐] Достижения", ""]
    shown = False
    for ach_id in get_achievement_order(chat_id):
        if ach_id not in unlocked:
            continue
        ach = get_achievement(chat_id, ach_id)
        if not ach:
            continue
        lines.append(format_achievement_line(ach))
        shown = True
    if not shown:
        lines.append("— пока нет —")
    return "\n".join(lines)


def try_unlock(
    chat_id: int, user_id: int, achievement_id: str
) -> AchievementDef | None:
    ach = get_achievement(chat_id, achievement_id)
    if not ach:
        return None
    if not db.grant_achievement(chat_id, user_id, achievement_id):
        return None
    return ach


def check_after_battle_rewards(
    chat_id: int,
    state: BattleState,
    winner_id: int,
    winner: Player,
    loser: Player,
) -> list[AchievementDef]:
    unlocked: list[AchievementDef] = []

    def _unlock(achievement_id: str) -> None:
        ach = try_unlock(chat_id, winner_id, achievement_id)
        if ach:
            unlocked.append(ach)

    winner_hp = state.hp_for(winner_id)
    winner_char = (
        state.p1_character if winner_id == state.p1_id else state.p2_character
    )

    if winner_hp > 75:
        _unlock("win_75hp")
    if loser.v_tier == "secret_v":
        _unlock("beat_secret_v")
    if winner_char == "loh":
        _unlock("win_as_loh")
    if winner.wins == 50:
        _unlock("wins_50")
    if winner.wins == 100:
        _unlock("wins_100")

    top = db.top_players_by_wins(chat_id, limit=1)
    if top and top[0].user_id == winner_id:
        _unlock("top1_first")

    return unlocked


def on_v1_action_used(chat_id: int, user_id: int) -> AchievementDef | None:
    return try_unlock(chat_id, user_id, "v1_first")


def on_virus_used(chat_id: int, user_id: int) -> AchievementDef | None:
    return try_unlock(chat_id, user_id, "virus_first")


def on_virus_death(chat_id: int, user_id: int) -> AchievementDef | None:
    return try_unlock(chat_id, user_id, "virus_death_first")


def on_secret_v_obtained(chat_id: int, user_id: int) -> AchievementDef | None:
    return try_unlock(chat_id, user_id, "secret_v_first")


def on_beam_demote(chat_id: int, user_id: int) -> AchievementDef | None:
    return try_unlock(chat_id, user_id, "beam_demote_first")


def on_v14bb_purchased(chat_id: int, user_id: int) -> AchievementDef | None:
    return try_unlock(chat_id, user_id, "v14bb_buy")
