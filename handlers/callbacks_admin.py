"""Callback выдачи персонажа и достижений админом."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from game import db
from game.achievements import (
    announce_unlock,
    delete_custom_achievement,
    format_achievement_line,
    get_achievement,
    get_achievement_order,
    try_unlock,
)
from game.characters import CHARACTER_NAMES, admin_assign_character
from handlers.admin_auth import require_bot_admin
from handlers.utils import display_name


def _achievement_by_index(chat_id: int, idx: int):
    order = get_achievement_order(chat_id)
    if idx < 0 or idx >= len(order):
        return None
    return get_achievement(chat_id, order[idx])


async def on_admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    if not await require_bot_admin(update):
        return
    await query.answer()

    parts = query.data.split(":")
    if len(parts) < 4 or parts[0] != "admin":
        return

    chat = query.message.chat if query.message else None
    if not chat:
        return
    chat_id = chat.id

    if parts[1] == "hero" and len(parts) == 4:
        char_id = parts[2]
        try:
            target_id = int(parts[3])
        except ValueError:
            return
        if char_id not in CHARACTER_NAMES:
            return

        player = db.get_or_create_player(chat_id, target_id)
        admin_assign_character(player, char_id)
        db.save_player(player)
        if player.v_tier == "secret_v":
            ach = try_unlock(chat_id, target_id, "secret_v_first")
            if ach:
                await announce_unlock(context.bot, chat_id, target_id, ach)

        name = CHARACTER_NAMES[char_id]
        tname = player.display_name or str(target_id)
        await query.edit_message_text(
            f"{tname} получил персонажа: {name} (V: {player.v_tier})."
        )
        return

    if parts[1] == "shop" and len(parts) == 4 and parts[2] in ("blk", "ubl"):
        from game.shop_items import SHOP_ITEMS, shop_item_label

        try:
            idx = int(parts[3])
        except ValueError:
            return
        if idx < 0 or idx >= len(SHOP_ITEMS):
            await query.edit_message_text("Товар не найден.")
            return
        item_id, _ = SHOP_ITEMS[idx]
        label = shop_item_label(item_id)
        if parts[2] == "blk":
            if db.block_shop_item(chat_id, item_id):
                await query.edit_message_text(f"🔒 Заблокирован: {label}")
            else:
                await query.edit_message_text(f"Уже заблокирован: {label}")
        else:
            if db.unblock_shop_item(chat_id, item_id):
                await query.edit_message_text(f"✅ Разблокирован: {label}")
            else:
                await query.edit_message_text("Товар не был заблокирован.")
        return

    if parts[1] == "achdef" and len(parts) == 4 and parts[2] == "del":
        try:
            idx = int(parts[3])
        except ValueError:
            return
        custom = db.list_chat_achievement_defs(chat_id)
        if idx < 0 or idx >= len(custom):
            await query.edit_message_text("Достижение не найдено.")
            return
        ach = custom[idx]
        if not delete_custom_achievement(chat_id, ach.id):
            await query.edit_message_text("Не удалось удалить достижение.")
            return
        await query.edit_message_text(
            f"Достижение удалено: {ach.title}\n"
            "Оно снято у всех игроков в этой беседе."
        )
        return

    if parts[1] == "ach" and len(parts) == 5 and parts[2] in ("g", "r"):
        action = parts[2]
        try:
            idx = int(parts[3])
            target_id = int(parts[4])
        except ValueError:
            return
        ach = _achievement_by_index(chat_id, idx)
        if not ach:
            return

        player = db.get_or_create_player(chat_id, target_id)
        tname = player.display_name or display_name(query.from_user)

        if action == "g":
            granted = try_unlock(chat_id, target_id, ach.id)
            if granted:
                await announce_unlock(context.bot, chat_id, target_id, granted)
                await query.edit_message_text(
                    f"{tname}: выдано достижение\n{format_achievement_line(granted)}"
                )
            else:
                await query.edit_message_text(
                    f"У {tname} уже есть: {ach.title}"
                )
            return

        if action == "r":
            if db.revoke_achievement(chat_id, target_id, ach.id):
                await query.edit_message_text(
                    f"{tname}: снято достижение «{ach.title}»"
                )
            else:
                await query.edit_message_text(
                    f"У {tname} нет достижения «{ach.title}»"
                )
