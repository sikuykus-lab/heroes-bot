"""Команды /start, /shop, /help, /profile."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from game import db
from game.achievements import format_achievements_block
from game.currency import display_amount
from game.characters import player_status_label
from game import promo as promo_logic
from game.keyboards import shop_keyboard
from handlers.utils import display_name, require_group


COMMANDS_LINES = """/start, /profile или «профиль пвп» — профиль
/profile @username — профиль игрока
/shop или «Магазин» — магазин
/fight или «Бой» — открытый вызов на бой
Ответ на сообщение «Бой/fight» — вызов игроку
/dropmoney сумма — перевод (ответом или тегом)
/code промокод — бонус при знании промо
/help — справка"""

COMMANDS_BLOCK = "Команды:\n" + COMMANDS_LINES
COMMANDS_TEXT = "[ 📋 ] Команды:\n" + COMMANDS_LINES

HELP_TEXT = """[ ❓ ] Важные моменты перед игрой!

1. Перед боем, лучше всего зайти в магазин и приобрести V (V24 / V / V1) — /shop.
2. Ходы — кнопки под сообщением боя, каждый из них пошаговый.
3. Важно заметить, каждая из применяемых вами способностей рассчитывают свою мощность взависимости от числа выпавшего вам от Кубика-Рубика, также большинство уворотов работают по системе Чётное/Нечётное где первое это успех а второе провал.
4. VCoins зарабатываются по истечению боя, их получает и победивший и проигравший игрок (если игрок сдался/сбежал, VCoins он не получит).
5. Если вы нашли баг/ошибку в боте то обращайтесь к одному из активных администраторов с отчетом об ошибке и скриншотами/видео."""


def _player(update: Update):
    user = update.effective_user
    chat = update.effective_chat
    return db.get_or_create_player(
        chat.id,
        user.id,
        display_name(user),
        user.username or "",
    )


def format_kd_ratio(wins: int, losses: int) -> str:
    if losses <= 0:
        return str(wins) if wins > 0 else "0"
    ratio = wins / losses
    text = f"{ratio:.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _format_v_tier(p) -> str:
    if p.v_tier == "none":
        return "нет (Лох)"
    if p.v_tier == "v14bb":
        return "V14BB"
    if p.v_tier == "secret_v":
        return "Secret V"
    tier = p.v_tier.upper()
    if p.v_tier == "v24":
        return f"{tier} (боев осталось: {p.v24_battles_left})"
    return tier


def format_profile_block(p, title: str = "Ваш игровой профиль") -> str:
    uname = f"@{p.telegram_username}" if p.telegram_username else "—"
    char = player_status_label(p.v_tier, p.active_character)
    cur = db.get_chat_currency(p.chat_id)
    balance = display_amount(cur, p.coins)
    return (
        f"{title}\n\n"
        f"• [ 👤 ] Имя: {p.display_name or 'Игрок'}\n"
        f"• [ 💳 ] Username: {uname}\n"
        f"• [ 💰 ] Баланс: {balance}\n"
        f"• [ 🧪 ] Уровень V: {_format_v_tier(p)}\n"
        f"• [ 🦸‍♂️ ] Персонаж: {char}\n"
        f"• [ 🧬 ] Вирус: {p.virus_count}\n"
        f"• [ 🏅 ] Всего побед: {p.wins}\n"
        f"• [ ⚰️ ] Всего поражений: {p.losses}\n"
        f"• [✨] K/D: {format_kd_ratio(p.wins, p.losses)}\n\n"
        f"{format_achievements_block(p.chat_id, p.user_id)}"
    )


PROFILE_CHANNELS_FOOTER = (
    "\n\n"
    "[ ⚡ ] Официальный канал TG — https://t.me/soboyssomems\n"
    "[ 📋 ] Официальный канал с обновлениями и патчами — https://t.me/homelandaheye"
)


def format_profile_message(p, title: str = "Ваш игровой профиль") -> str:
    return format_profile_block(p, title=title) + PROFILE_CHANNELS_FOOTER


def format_shop_text(p) -> str:
    char = player_status_label(p.v_tier, p.active_character)
    cur = db.get_chat_currency(p.chat_id)
    return (
        "🛒 Магазин\n\n"
        f"• [ 💰 ] Баланс: {display_amount(cur, p.coins)}\n"
        f"• [ 🧪 ] Текущий V: {_format_v_tier(p)}\n"
        f"• [ 🦸‍♂️ ] Персонаж: {char}"
    )


def _resolve_profile_user_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    msg = update.message
    if not msg or not update.effective_user:
        return update.effective_user.id if update.effective_user else None

    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
        if not target.is_bot:
            return target.id

    for ent in msg.entities or []:
        if ent.type == "text_mention" and ent.user and not ent.user.is_bot:
            return ent.user.id

    if context.args:
        arg = context.args[0].lstrip("@")
        found = db.find_player_by_username(update.effective_chat.id, arg)
        if found:
            return found.user_id
        return None

    return update.effective_user.id


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    p = _player(update)
    text = (
        "Глаз Твердыни - Приветствует!\n\n"
        f"{format_profile_block(p)}\n\n"
        f"{COMMANDS_BLOCK}\n\n"
        "[ ⚡ ] Официальный канал TG — https://t.me/soboyssomems\n"
        "[ 📋 ] Официальный канал с обновлениями и патчами — https://t.me/homelandaheye"
    )
    await update.message.reply_text(text)


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    chat_id = update.effective_chat.id
    target_id = _resolve_profile_user_id(update, context)

    if target_id is None:
        await update.message.reply_text(
            "Игрок не найден. Укажите @username из беседы (нужен /start у игрока) "
            "или ответьте на его сообщение."
        )
        return

    if target_id == update.effective_user.id:
        p = _player(update)
        await update.message.reply_text(format_profile_message(p))
        return

    target_user = None
    if update.message and update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    for ent in update.message.entities or [] if update.message else []:
        if ent.type == "text_mention" and ent.user and ent.user.id == target_id:
            target_user = ent.user
            break

    dname = display_name(target_user) if target_user else "Игрок"
    uname = (target_user.username or "") if target_user else ""
    p = db.get_or_create_player(chat_id, target_id, dname, uname)
    await update.message.reply_text(
        format_profile_message(p, title="Игровой профиль")
    )


async def cmd_commands(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    await update.message.reply_text(COMMANDS_TEXT)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    await update.message.reply_text(HELP_TEXT)


async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    p = _player(update)
    await update.message.reply_text(
        format_shop_text(p), reply_markup=shop_keyboard(p)
    )


def format_top_pvp(chat_id: int) -> str:
    top = db.top_players_by_wins(chat_id, limit=15)
    lines = ["[ 🏆 ] Глобальный топ игроков", ""]
    for rank in range(1, 16):
        if rank <= len(top):
            p = top[rank - 1]
            name = p.display_name or "Игрок"
            kd = format_kd_ratio(p.wins, p.losses)
            info = f" {name} [K/D: {kd}] — {p.wins}"
        else:
            info = ""
        if rank == 1:
            lines.append(f"• 1 [🌟]{info}")
        else:
            lines.append(f"• {rank}{info}")
    return "\n".join(lines)


async def cmd_toppvp(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    await update.message.reply_text(
        format_top_pvp(update.effective_chat.id)
    )


async def cmd_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /code промокод")
        return
    p = _player(update)
    result = promo_logic.redeem_promo(p, context.args[0])
    await update.message.reply_text(result.message)
