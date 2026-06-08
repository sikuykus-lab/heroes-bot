"""Callback магазина (inline-кнопки)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from game import db
from game.achievements import announce_unlock
from game import shop as shop_logic
from game.shop_items import shop_item_label
from game.keyboards import shop_keyboard
from handlers.commands import format_shop_text
from handlers.utils import display_name, require_group


def _shop_text(player, extra: str = "") -> str:
    text = format_shop_text(player)
    if extra:
        text = f"{extra}\n\n{text}"
    return text


async def on_shop_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data or not query.from_user:
        return
    await query.answer()

    chat = query.message.chat if query.message else None
    if not chat or chat.type not in ("group", "supergroup"):
        return

    chat_id = chat.id
    user_id = query.from_user.id
    player = db.get_or_create_player(
        chat_id,
        user_id,
        display_name(query.from_user),
        query.from_user.username or "",
    )
    action = query.data.split(":", 1)[1]

    if db.is_shop_item_blocked(chat_id, action):
        await query.answer(
            f"«{shop_item_label(action)}» заблокирован админом.",
            show_alert=True,
        )
        return

    handlers_map = {
        "v24_free": shop_logic.claim_v24_free,
        "v24_paid": shop_logic.buy_v24_paid,
        "v": shop_logic.buy_v,
        "v1": shop_logic.buy_v1,
        "v14bb": shop_logic.buy_v14bb,
        "virus": shop_logic.buy_virus,
    }
    fn = handlers_map.get(action)
    if not fn:
        return
    result = fn(player)
    player = db.get_or_create_player(chat_id, user_id, player.display_name)
    if result.new_achievement:
        await announce_unlock(
            context.bot, chat_id, user_id, result.new_achievement
        )
    await query.edit_message_text(
        _shop_text(player, result.message),
        reply_markup=shop_keyboard(player),
    )
