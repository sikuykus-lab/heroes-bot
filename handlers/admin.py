"""Админ-команды беседы."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from game import db
from game.achievements import (
    ACHIEVEMENTS,
    create_custom_achievement,
    delete_custom_achievement,
    format_achievement_line,
    get_achievement,
    get_achievement_order,
)
from game.achievements import on_beam_demote as achievement_beam_demote
from game.achievements import announce_unlock
from game.charge_beam import demote_user_to_loh
from game.config import V24_BATTLES
from game.stickers import soldier_beam_sticker_file_id
from game.characters import (
    CHARACTER_NAMES,
    admin_assign_character,
    admin_clear_hero,
    ALL_CHARACTER_IDS,
    apply_super_promotion,
)
from game.currency import (
    currency_title,
    display_amount,
    from_display_units,
    normalize_currency_arg,
)
from handlers.admin_auth import (
    is_bot_admin,
    is_chat_creator,
    parse_amount_and_reason,
    parse_positive_amount,
    require_bot_admin,
    require_bot_staff,
    require_cancel_fights,
    resolve_mentioned_users,
    resolve_money_target,
    resolve_target_user,
)
from handlers.battle_admin import force_cancel_battle
from handlers.utils import display_name, require_group

def _hero_picker_keyboard(target_user_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for cid in ALL_CHARACTER_IDS:
        name = CHARACTER_NAMES[cid]
        row.append(
            InlineKeyboardButton(
                name,
                callback_data=f"admin:hero:{cid}:{target_user_id}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _achievement_label(ach) -> str:
    label = ach.title[:32]
    if ach.exclusive and not ach.emoji:
        label = f"⚡ {label}"[:32]
    elif ach.emoji:
        label = f"{ach.emoji} {label}"[:32]
    return label


def _achievement_grant_keyboard(chat_id: int, target_user_id: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx, ach_id in enumerate(get_achievement_order(chat_id)):
        ach = get_achievement(chat_id, ach_id)
        if not ach:
            continue
        row.append(
            InlineKeyboardButton(
                _achievement_label(ach),
                callback_data=f"admin:ach:g:{idx}:{target_user_id}",
            )
        )
        if len(row) == 1:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def _achievement_revoke_keyboard(
    chat_id: int, target_user_id: int
) -> InlineKeyboardMarkup | None:
    unlocked = set(db.list_player_achievements(chat_id, target_user_id))
    if not unlocked:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for idx, ach_id in enumerate(get_achievement_order(chat_id)):
        if ach_id not in unlocked:
            continue
        ach = get_achievement(chat_id, ach_id)
        if not ach:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    ach.title[:32],
                    callback_data=f"admin:ach:r:{idx}:{target_user_id}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows) if rows else None


def _achievement_delete_keyboard(chat_id: int) -> InlineKeyboardMarkup | None:
    custom = db.list_chat_achievement_defs(chat_id)
    if not custom:
        return None
    rows: list[list[InlineKeyboardButton]] = []
    for idx, ach in enumerate(custom):
        rows.append(
            [
                InlineKeyboardButton(
                    ach.title[:40],
                    callback_data=f"admin:achdef:del:{idx}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows)


async def cmd_addach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    actor = update.effective_user
    target = resolve_target_user(update.message, actor)
    tname = display_name(target)
    await update.message.reply_text(
        f"Выберите достижение для {tname}:",
        reply_markup=_achievement_grant_keyboard(chat_id, target.id),
    )


async def cmd_clearach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    actor = update.effective_user
    target = resolve_target_user(update.message, actor)
    kb = _achievement_revoke_keyboard(chat_id, target.id)
    if not kb:
        await update.message.reply_text(
            f"У {display_name(target)} нет достижений."
        )
        return
    await update.message.reply_text(
        f"Снять достижение у {display_name(target)}:",
        reply_markup=kb,
    )


async def cmd_createach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    if not update.message or not update.effective_chat:
        return
    context.user_data["createach"] = {
        "step": "title",
        "chat_id": update.effective_chat.id,
    }
    await update.message.reply_text(
        "📝 Создание достижения.\n"
        "Введите название достижения:"
    )


async def process_createach_step(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> bool:
    """Обработка шагов /createach. True — сообщение обработано."""
    state = context.user_data.get("createach")
    if not state or not update.message or not update.message.text:
        return False
    if update.message.text.startswith("/"):
        context.user_data.pop("createach", None)
        return False
    if not update.effective_chat or state.get("chat_id") != update.effective_chat.id:
        return False
    if not await is_bot_admin(update):
        context.user_data.pop("createach", None)
        return False

    text = update.message.text.strip()
    if not text:
        await update.message.reply_text("Текст не может быть пустым.")
        return True

    chat_id = update.effective_chat.id
    step = state["step"]
    if step == "title":
        state["title"] = text
        state["step"] = "criteria"
        await update.message.reply_text("Введите заслугу (текст в квадратных скобках):")
        return True

    if step == "criteria":
        ach = create_custom_achievement(chat_id, state["title"], text)
        context.user_data.pop("createach", None)
        await update.message.reply_text(
            "✅ Достижение создано:\n"
            f"{format_achievement_line(ach)}\n\n"
            "Выдавайте игрокам через /addach."
        )
        return True

    context.user_data.pop("createach", None)
    return False


async def cmd_deleteach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    kb = _achievement_delete_keyboard(chat_id)
    if not kb:
        await update.message.reply_text(
            "Нет созданных достижений для удаления.\n"
            "Создайте своё через /createach."
        )
        return
    await update.message.reply_text(
        "Выберите достижение для удаления (только созданные через /createach):",
        reply_markup=kb,
    )


def _shop_block_keyboard(chat_id: int) -> InlineKeyboardMarkup | None:
    from game.shop_items import SHOP_ITEMS

    blocked = set(db.list_blocked_shop_items(chat_id))
    rows: list[list[InlineKeyboardButton]] = []
    for idx, (item_id, label) in enumerate(SHOP_ITEMS):
        if item_id in blocked:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    f"🔒 {label[:40]}",
                    callback_data=f"admin:shop:blk:{idx}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows) if rows else None


def _shop_unblock_keyboard(chat_id: int) -> InlineKeyboardMarkup | None:
    from game.shop_items import SHOP_ITEMS, shop_item_label

    blocked = db.list_blocked_shop_items(chat_id)
    if not blocked:
        return None
    blocked_set = set(blocked)
    rows: list[list[InlineKeyboardButton]] = []
    for idx, (item_id, _label) in enumerate(SHOP_ITEMS):
        if item_id not in blocked_set:
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    shop_item_label(item_id)[:40],
                    callback_data=f"admin:shop:ubl:{idx}",
                )
            ]
        )
    return InlineKeyboardMarkup(rows) if rows else None


async def cmd_blockshop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    kb = _shop_block_keyboard(chat_id)
    if not kb:
        await update.message.reply_text("Все товары магазина уже заблокированы.")
        return
    await update.message.reply_text(
        "Выберите товар для блокировки покупки:",
        reply_markup=kb,
    )


async def cmd_unblockshop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    kb = _shop_unblock_keyboard(chat_id)
    if not kb:
        await update.message.reply_text("Нет заблокированных товаров.")
        return
    await update.message.reply_text(
        "Выберите товар для разблокировки:",
        reply_markup=kb,
    )


async def cmd_staff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    if not update.message or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    actor = update.effective_user
    hit = resolve_money_target(update.message, actor, chat_id, context.args or [])
    if not hit:
        await update.message.reply_text(
            "Укажите пользователя: ответьте на сообщение или упомяните @username."
        )
        return
    db.add_bot_staff(chat_id, hit.user_id, actor.id)
    await update.message.reply_text(
        f"{hit.name} назначен staff бота (доступ: /rv24, /cancelcalls)."
    )


async def cmd_destaff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    if not update.message or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    actor = update.effective_user
    hit = resolve_money_target(update.message, actor, chat_id, context.args or [])
    if not hit:
        await update.message.reply_text(
            "Укажите пользователя: ответьте на сообщение или упомяните @username."
        )
        return
    was_staff, was_senior = db.remove_bot_staff_roles(chat_id, hit.user_id)
    if not was_staff and not was_senior:
        await update.message.reply_text(f"У {hit.name} нет роли staff.")
        return
    roles = []
    if was_staff:
        roles.append("staff")
    if was_senior:
        roles.append("старший staff")
    await update.message.reply_text(
        f"У {hit.name} сняты роли: {', '.join(roles)}."
    )


async def cmd_ststaff(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    if not update.message or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    actor = update.effective_user
    hit = resolve_money_target(update.message, actor, chat_id, context.args or [])
    if not hit:
        await update.message.reply_text(
            "Укажите пользователя: ответьте на сообщение или упомяните @username."
        )
        return
    db.add_bot_staff(chat_id, hit.user_id, actor.id)
    db.add_bot_senior_staff(chat_id, hit.user_id, actor.id)
    await update.message.reply_text(
        f"{hit.name} назначен старшим staff бота "
        f"(доступ: /rv24, /cancelcalls, /cancelfights)."
    )


async def cmd_op(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await is_chat_creator(update):
        await update.message.reply_text(
            "Только владелец беседы может выдавать права администратора бота."
        )
        return
    actor = update.effective_user
    target = resolve_target_user(update.message, actor)
    if target.id == actor.id:
        await update.message.reply_text(
            "Укажите пользователя: ответьте на его сообщение или /op с упоминанием."
        )
        return
    db.add_bot_admin(update.effective_chat.id, target.id, actor.id)
    name = display_name(target)
    await update.message.reply_text(
        f"{name} назначен администратором бота в этой беседе."
    )


async def cmd_addhero(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    actor = update.effective_user
    target = resolve_target_user(update.message, actor)
    tname = display_name(target)
    await update.message.reply_text(
        f"Выберите персонажа для {tname}:",
        reply_markup=_hero_picker_keyboard(target.id),
    )


async def cmd_clearhero(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    actor = update.effective_user
    target = resolve_target_user(update.message, actor)
    player = db.get_or_create_player(chat_id, target.id, display_name(target))
    admin_clear_hero(player)
    db.save_player(player)
    await update.message.reply_text(
        f"{display_name(target)} снова Лох (V и персонаж сброшены)."
    )


async def cmd_addmoney(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    amount_disp, _reason = parse_amount_and_reason(context.args or [])
    if amount_disp is None:
        await update.message.reply_text("Использование: /addmoney 500 (ответом на игрока — ему)")
        return
    chat_id = update.effective_chat.id
    cur = db.get_chat_currency(chat_id)
    add_vcoin = from_display_units(cur, amount_disp)
    actor = update.effective_user
    target = resolve_target_user(update.message, actor)
    player = db.get_or_create_player(chat_id, target.id, display_name(target))
    player.coins += add_vcoin
    db.save_player(player)
    await update.message.reply_text(
        f"+{display_amount(cur, add_vcoin)} → {display_name(target)} "
        f"(баланс: {display_amount(cur, player.coins)})."
    )


async def cmd_changevalue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    if not context.args:
        cur = db.get_chat_currency(update.effective_chat.id)
        await update.message.reply_text(
            f"Валюта чата: {currency_title(cur)}.\n"
            "Использование: /changevalue vcoins или /changevalue rubles"
        )
        return
    new_cur = normalize_currency_arg(context.args[0])
    if not new_cur:
        await update.message.reply_text(
            "Доступно: vcoins (VCoins) или rubles (Рубли)."
        )
        return
    chat_id = update.effective_chat.id
    old_cur = db.get_chat_currency(chat_id)
    if old_cur == new_cur:
        await update.message.reply_text(f"Уже используется {currency_title(new_cur)}.")
        return
    db.set_chat_currency(chat_id, new_cur)
    from game.config import RUBLES_PER_VCOIN

    await update.message.reply_text(
        f"Валюта чата: {currency_title(old_cur)} → {currency_title(new_cur)}.\n"
        f"Курс: 1 VCoin = {RUBLES_PER_VCOIN} ₽ (балансы в базе не меняются, меняется отображение)."
    )


async def cmd_changelimits(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    if not context.args:
        limit = db.get_max_open_challenges(chat_id)
        await update.message.reply_text(
            f"Лимит открытых вызовов в чате: {limit}.\n"
            "Использование: /changelimits 5"
        )
        return
    amount = parse_positive_amount(context.args)
    if amount is None:
        await update.message.reply_text(
            "Укажите число от 1. Пример: /changelimits 5"
        )
        return
    old = db.get_max_open_challenges(chat_id)
    db.set_max_open_challenges(chat_id, amount)
    await update.message.reply_text(
        f"Лимит открытых вызовов: {old} → {amount}."
    )


async def cmd_changefights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    if not context.args:
        limit = db.get_max_active_battles(chat_id)
        await update.message.reply_text(
            f"Лимит одновременных боёв в чате: {limit}.\n"
            "Использование: /changefights 5"
        )
        return
    amount = parse_positive_amount(context.args)
    if amount is None:
        await update.message.reply_text(
            "Укажите число от 1. Пример: /changefights 5"
        )
        return
    old = db.get_max_active_battles(chat_id)
    db.set_max_active_battles(chat_id, amount)
    await update.message.reply_text(
        f"Лимит одновременных боёв: {old} → {amount}."
    )


async def cmd_cheats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    text = (update.message.text or "").lower() if update.message else ""
    arg = (context.args[0].lower() if context.args else "") or ""
    if arg in ("on", "1", "вкл") or "включ" in text:
        enable = True
    elif arg in ("off", "0", "выкл") or "выключ" in text:
        enable = False
    else:
        state = "включены" if db.get_chat_cheats_enabled(chat_id) else "выключены"
        await update.message.reply_text(
            f"Читы в чате: {state}.\n"
            "Использование: /cheats on или /cheats off\n"
            "Алиасы: /включитьчиты · /выключитьчиты"
        )
        return
    db.set_chat_cheats_enabled(chat_id, enable)
    await update.message.reply_text(
        f"Читы {'включены' if enable else 'выключены'}. "
        + (
            "У админов в бою всегда выпадает 6."
            if enable
            else "Бросок кубика снова обычный."
        )
    )


async def cmd_cheats_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.args = ["on"]
    await cmd_cheats(update, context)


async def cmd_cheats_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.args = ["off"]
    await cmd_cheats(update, context)


async def cmd_nalog(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    amount_disp, reason = parse_amount_and_reason(context.args or [])
    if amount_disp is None:
        await update.message.reply_text(
            "Использование: /nalog 500 [причина]"
        )
        return
    chat_id = update.effective_chat.id
    cur = db.get_chat_currency(chat_id)
    deduct = from_display_units(cur, amount_disp)
    if deduct <= 0:
        await update.message.reply_text("Сумма слишком мала для текущей валюты чата.")
        return
    players = db.list_players_in_chat(chat_id)
    for player in players:
        player.coins = max(0, player.coins - deduct)
        db.save_player(player)
    reason_line = f"\nПричина: {reason}" if reason else ""
    await update.message.reply_text(
        f"Налог {display_amount(cur, deduct)} с каждого игрока ({len(players)} чел.)."
        f"{reason_line}"
    )


async def cmd_shtraf(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    amount_disp, reason = parse_amount_and_reason(context.args or [])
    if amount_disp is None:
        await update.message.reply_text(
            "Использование: /shtraf 500 [причина] — ответом или тегом на игрока"
        )
        return
    if not update.message or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    actor = update.effective_user
    target = resolve_money_target(
        update.message, actor, chat_id, context.args or []
    )
    if not target:
        await update.message.reply_text(
            "Укажите игрока: ответьте на сообщение или упомяните @username."
        )
        return
    cur = db.get_chat_currency(chat_id)
    deduct = from_display_units(cur, amount_disp)
    if deduct <= 0:
        await update.message.reply_text("Сумма слишком мала для текущей валюты чата.")
        return
    player = db.get_or_create_player(chat_id, target.user_id, target.name)
    player.coins = max(0, player.coins - deduct)
    db.save_player(player)
    reason_line = f"\nПричина: {reason}" if reason else ""
    await update.message.reply_text(
        f"Штраф {display_amount(cur, deduct)} — {target.name} "
        f"(баланс: {display_amount(cur, player.coins)})."
        f"{reason_line}"
    )


async def _require_soldier_admin(update: Update) -> bool:
    if not await require_group(update):
        return False
    if not await is_bot_admin(update):
        return False
    if not update.effective_user or not update.message:
        return False
    chat_id = update.effective_chat.id
    actor = update.effective_user
    player = db.get_or_create_player(
        chat_id, actor.id, display_name(actor)
    )
    if player.active_character != "soldier_boy":
        await update.message.reply_text(
            "Команда только для администратора с персонажем Солдатик."
        )
        return False
    return True


async def _send_charge_beam(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    targets: list[tuple[int, str]],
    *,
    attacker_name: str,
) -> None:
    msg = update.message
    if not msg:
        return
    chat_id = update.effective_chat.id
    names: list[str] = []
    for user_id, name in targets:
        demote_user_to_loh(chat_id, user_id)
        ach = achievement_beam_demote(chat_id, user_id)
        if ach:
            await announce_unlock(context.bot, chat_id, user_id, ach)
        names.append(name)

    if len(names) == 1:
        caption = (
            f"☢️ {attacker_name} выпустил луч!\n"
            f"{names[0]} потерял способности и стал Лохом."
        )
    else:
        victims = ", ".join(names)
        caption = (
            f"☢️ {attacker_name} выпустил луч по всем!\n"
            f"Лохами стали: {victims}."
        )

    sticker_id = await soldier_beam_sticker_file_id(
        context.bot, context.application.bot_data
    )
    if sticker_id:
        await msg.reply_sticker(sticker=sticker_id)
        await msg.reply_text(caption)
    else:
        await msg.reply_text(caption + "\n\n(стикер-пак SoldierBeam недоступен боту)")


async def cmd_chargebeam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Вне боя: луч по цели (reply/тег) или /chargebeam everyone."""
    if not await _require_soldier_admin(update):
        return
    if not update.message or not update.effective_user:
        return

    actor = update.effective_user
    chat_id = update.effective_chat.id
    in_battle = db.user_ids_in_active_battles(chat_id)
    args = [a.lower() for a in (context.args or [])]
    attacker_name = display_name(actor)

    if args and args[0] == "everyone":
        hit: list[tuple[int, str]] = []
        for player in db.list_players_in_chat(chat_id):
            if player.user_id == actor.id or player.user_id in in_battle:
                continue
            hit.append(
                (player.user_id, player.display_name or "Игрок")
            )
        if not hit:
            await update.message.reply_text(
                "Нет игроков вне боя (все в бою или только вы в базе)."
            )
            return
        await _send_charge_beam(
            update, context, hit, attacker_name=attacker_name
        )
        return

    users = resolve_mentioned_users(update.message)
    if not users:
        await update.message.reply_text(
            "Укажите цель: ответьте на сообщение, тегните игрока "
            "или /chargebeam everyone"
        )
        return

    hit = [
        (u.id, display_name(u))
        for u in users
        if u.id not in in_battle
    ]
    if not hit:
        await update.message.reply_text(
            "Цель в активном бою — луч по ней нельзя. "
            "Можно бить игроков вне боя, пока идут чужие бои."
        )
        return
    await _send_charge_beam(
        update, context, hit, attacker_name=attacker_name
    )


async def cmd_beam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Секрет: заряд луча Солдатика до 100% в активном бою беседы."""
    if not await require_group(update):
        return
    if not await is_bot_admin(update):
        return
    chat_id = update.effective_chat.id
    charged: list[int] = []
    for battle_id, p1_id, p2_id, state in db.list_active_battles(chat_id):
        touched = False
        for uid in (p1_id, p2_id):
            char = (
                state.p1_character if uid == state.p1_id else state.p2_character
            )
            if char == "soldier_boy":
                state.status_for(uid).soldier_beam_pct = 100
                touched = True
        if touched:
            db.save_battle(battle_id, chat_id, p1_id, p2_id, state)
            charged.append(battle_id)

    msg = update.message
    if not charged:
        text = "Нет активного боя с Солдатиком."
    elif len(charged) == 1:
        text = f"☢️ Луч заряжен на 100% (бой #{charged[0]})."
    else:
        ids = ", ".join(f"#{b}" for b in charged)
        text = f"☢️ Луч 100% в боях: {ids}."

    reply = await msg.reply_text(text)
    try:
        await msg.delete()
        await reply.delete()
    except Exception:
        pass


async def cmd_rv24(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Выдать игроку случайный V24 на два боя (ответом на сообщение)."""
    if not await require_group(update):
        return
    if not await require_bot_staff(update):
        return
    if not update.message:
        return
    actor = update.effective_user
    target = resolve_target_user(update.message, actor)
    if target.id == actor.id and not update.message.reply_to_message:
        await update.message.reply_text(
            "Ответьте на сообщение игрока, которому выдать V24."
        )
        return
    chat_id = update.effective_chat.id
    player = db.get_or_create_player(chat_id, target.id, display_name(target))
    player.v_tier = "v24"
    player.v24_battles_left = V24_BATTLES
    apply_super_promotion(player, roll=True)
    db.save_player(player)
    hero = CHARACTER_NAMES.get(player.active_character, player.active_character)
    await update.message.reply_text(
        f"{display_name(target)} получил V24 на {V24_BATTLES} боя.\n"
        f"Выпал: {hero}."
    )


async def cmd_cancelfights(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отмена боёв: все в чате или бой по ответу на его сообщение."""
    if not await require_group(update):
        return
    if not await require_cancel_fights(update):
        return
    if not update.message:
        return

    chat_id = update.effective_chat.id
    reply = update.message.reply_to_message

    if reply:
        found = db.find_battle_by_message_id(chat_id, reply.message_id)
        if not found:
            await update.message.reply_text(
                "Бой не найден. Ответьте на сообщение боя бота."
            )
            return
        battle_id, p1_id, p2_id, state = found
        await force_cancel_battle(
            context,
            chat_id,
            battle_id,
            p1_id,
            p2_id,
            state,
            reason="Бой отменён администратором.",
        )
        await update.message.reply_text(f"Бой #{battle_id} отменён.")
        return

    battles = db.list_active_battles(chat_id)
    if not battles:
        await update.message.reply_text("Активных боёв нет.")
        return

    for battle_id, p1_id, p2_id, state in battles:
        await force_cancel_battle(
            context,
            chat_id,
            battle_id,
            p1_id,
            p2_id,
            state,
            reason="Бой отменён администратором.",
        )
    await update.message.reply_text(f"Отменено боёв: {len(battles)}.")


async def cmd_cancelcalls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отмена всех активных вызовов на бой в беседе."""
    if not await require_group(update):
        return
    if not await require_bot_staff(update):
        return
    if not update.message:
        return

    chat_id = update.effective_chat.id
    challenges = db.list_open_challenges(chat_id)
    if not challenges:
        await update.message.reply_text("Активных вызовов нет.")
        return

    for ch in challenges:
        msg_id = ch.get("message_id")
        db.delete_challenge_by_id(ch["id"])
        db.clear_pending_loh_for_challenge(ch["id"])
        if msg_id:
            try:
                await context.bot.edit_message_text(
                    "Вызов отменён администратором.",
                    chat_id=chat_id,
                    message_id=msg_id,
                )
            except Exception:
                pass

    await update.message.reply_text(
        f"Отменено вызовов: {len(challenges)}."
    )


async def cmd_clearmoney(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await require_group(update):
        return
    if not await require_bot_admin(update):
        return
    amount_disp, _reason = parse_amount_and_reason(context.args or [])
    if amount_disp is None:
        await update.message.reply_text(
            "Использование: /clearmoney 500 (ответом на игрока — у него)"
        )
        return
    chat_id = update.effective_chat.id
    cur = db.get_chat_currency(chat_id)
    deduct = from_display_units(cur, amount_disp)
    actor = update.effective_user
    target = resolve_target_user(update.message, actor)
    player = db.get_or_create_player(chat_id, target.id, display_name(target))
    player.coins = max(0, player.coins - deduct)
    db.save_player(player)
    await update.message.reply_text(
        f"−{display_amount(cur, deduct)} у {display_name(target)} "
        f"(баланс: {display_amount(cur, player.coins)})."
    )
