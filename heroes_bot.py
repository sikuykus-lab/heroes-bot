"""
Telegram-бот «Супергерои» — PvP в супергруппе.
Запуск: python heroes_bot.py
"""

from __future__ import annotations

import logging
import os
import re

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    ApplicationHandlerStop,
    CallbackQueryHandler,
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from game.config import MINIAPP_ENABLED
from game.db import init_db
from handlers import (
    admin,
    money,
    callbacks_admin,
    callbacks_battle,
    callbacks_fight,
    callbacks_shop,
    channel_broadcast,
    commands,
    fight,
    miniapp_server,
    welcome,
)
from game.config import CHANNEL_BROADCAST_USERNAME
from handlers.commands import show_shop

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

SHOP_PATTERN = re.compile(r"(?i)^\s*(магазин|/shop)\s*@?\w*\s*$")
PROFILE_PATTERN = re.compile(
    r"(?i)^\s*(профиль\s*пвп|/profile)\s*@?\w*\s*$"
)
HELP_PATTERN = re.compile(r"(?i)^\s*(помощь|/help)\s*@?\w*\s*$")
TOP_PVP_PATTERN = re.compile(r"(?i)^\s*(топ\s*пвп|/toppvp)\s*@?\w*\s*$")
CHEATS_ON_PATTERN = re.compile(
    r"(?i)^\s*(/cheats\s+on|включить\s*читы|/включитьчиты)\s*@?\w*\s*$"
)
CHEATS_OFF_PATTERN = re.compile(
    r"(?i)^\s*(/cheats\s+off|выключить\s*читы|/выключитьчиты)\s*@?\w*\s*$"
)


async def on_top_pvp_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if TOP_PVP_PATTERN.match(update.message.text.strip()):
        await commands.cmd_toppvp(update, context)


async def on_help_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if HELP_PATTERN.match(update.message.text.strip()):
        await commands.cmd_help(update, context)


async def on_createach_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await admin.process_createach_step(update, context):
        raise ApplicationHandlerStop


async def on_shop_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if SHOP_PATTERN.match(update.message.text.strip()):
        await show_shop(update, context)


async def on_profile_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if PROFILE_PATTERN.match(update.message.text.strip()):
        await commands.cmd_profile(update, context)


async def on_cheats_on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if CHEATS_ON_PATTERN.match(update.message.text.strip()):
        context.args = ["on"]
        await admin.cmd_cheats(update, context)


async def on_cheats_off_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if CHEATS_OFF_PATTERN.match(update.message.text.strip()):
        context.args = ["off"]
        await admin.cmd_cheats(update, context)


async def _warm_caches(app: Application) -> None:
    from game.stickers import soldier_beam_sticker_file_id
    from handlers.battle_admin import schedule_battle_inactivity_checks

    fid = await soldier_beam_sticker_file_id(app.bot, app.bot_data)
    if fid:
        logger.info("Стикер SoldierBeam загружен")
    else:
        logger.warning(
            "Стикер-пак SoldierBeam недоступен — добавьте набор боту или проверьте имя"
        )
    schedule_battle_inactivity_checks(app)


async def _start_miniapp(_app: Application) -> None:
    await _warm_caches(_app)
    if not MINIAPP_ENABLED:
        logger.info("Mini App отключён (MINIAPP_ENABLED=0)")
        return
    token = _app.bot.token
    runner = await miniapp_server.start_miniapp_server(token)
    _app.bot_data["miniapp_runner"] = runner


async def _stop_miniapp(app: Application) -> None:
    runner = app.bot_data.get("miniapp_runner")
    if runner:
        await runner.cleanup()


def main() -> None:
    token = os.getenv("HEROES_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not token:
        raise SystemExit("Задайте HEROES_BOT_TOKEN in .env")

    init_db()

    app = (
        Application.builder()
        .token(token)
        .post_init(_start_miniapp)
        .post_shutdown(_stop_miniapp)
        .build()
    )

    app.add_handler(CommandHandler("start", commands.cmd_start))
    app.add_handler(CommandHandler("profile", commands.cmd_profile))
    app.add_handler(CommandHandler("help", commands.cmd_help))
    app.add_handler(CommandHandler("commands", commands.cmd_commands))
    app.add_handler(CommandHandler("shop", show_shop))
    app.add_handler(CommandHandler("code", commands.cmd_code))
    app.add_handler(CommandHandler("fight", fight.handle_fight_message))

    app.add_handler(CommandHandler("toppvp", commands.cmd_toppvp))
    app.add_handler(CommandHandler("op", admin.cmd_op))
    app.add_handler(CommandHandler("addhero", admin.cmd_addhero))
    app.add_handler(CommandHandler("clearhero", admin.cmd_clearhero))
    app.add_handler(CommandHandler("addach", admin.cmd_addach))
    app.add_handler(CommandHandler("clearach", admin.cmd_clearach))
    app.add_handler(CommandHandler("createach", admin.cmd_createach))
    app.add_handler(CommandHandler("deleteach", admin.cmd_deleteach))
    app.add_handler(CommandHandler("blockshop", admin.cmd_blockshop))
    app.add_handler(CommandHandler("unblockshop", admin.cmd_unblockshop))
    app.add_handler(CommandHandler("dropmoney", money.cmd_dropmoney))
    app.add_handler(CommandHandler("addmoney", admin.cmd_addmoney))
    app.add_handler(CommandHandler("clearmoney", admin.cmd_clearmoney))
    app.add_handler(CommandHandler("changevalue", admin.cmd_changevalue))
    app.add_handler(CommandHandler("changelimits", admin.cmd_changelimits))
    app.add_handler(CommandHandler("changefights", admin.cmd_changefights))
    app.add_handler(CommandHandler("cheats", admin.cmd_cheats))
    app.add_handler(CommandHandler("nalog", admin.cmd_nalog))
    app.add_handler(CommandHandler("shtraf", admin.cmd_shtraf))
    app.add_handler(CommandHandler("staff", admin.cmd_staff))
    app.add_handler(CommandHandler("destaff", admin.cmd_destaff))
    app.add_handler(CommandHandler("ststaff", admin.cmd_ststaff))
    app.add_handler(CommandHandler("cancelcalls", admin.cmd_cancelcalls))
    app.add_handler(CommandHandler("cancelfights", admin.cmd_cancelfights))
    app.add_handler(CommandHandler("rv24", admin.cmd_rv24))
    app.add_handler(CommandHandler("beam", admin.cmd_beam))
    app.add_handler(CommandHandler("chargebeam", admin.cmd_chargebeam))

    app.add_handler(
        ChatMemberHandler(
            welcome.on_bot_added_to_group,
            ChatMemberHandler.MY_CHAT_MEMBER,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome.on_bot_joined_via_message,
        )
    )
    channel_filter = filters.UpdateType.CHANNEL_POST & filters.Chat(
        username=CHANNEL_BROADCAST_USERNAME
    )
    app.add_handler(
        MessageHandler(channel_filter, channel_broadcast.on_channel_post)
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            on_createach_text,
        ),
        group=-1,
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(SHOP_PATTERN),
            on_shop_text,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(PROFILE_PATTERN),
            on_profile_text,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(TOP_PVP_PATTERN),
            on_top_pvp_text,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(CHEATS_ON_PATTERN),
            on_cheats_on_text,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(CHEATS_OFF_PATTERN),
            on_cheats_off_text,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & filters.Regex(HELP_PATTERN),
            on_help_text,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            fight.handle_fight_message,
        )
    )

    app.add_handler(CallbackQueryHandler(callbacks_shop.on_shop_callback, pattern=r"^shop:"))
    app.add_handler(CallbackQueryHandler(callbacks_fight.on_fight_callback, pattern=r"^fight:"))
    app.add_handler(CallbackQueryHandler(callbacks_battle.on_battle_callback, pattern=r"^battle:"))
    app.add_handler(CallbackQueryHandler(callbacks_admin.on_admin_callback, pattern=r"^admin:"))

    logger.info("Heroes bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
