"""Константы игры."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("HEROES_DB_PATH", str(ROOT / "heroes_game.db")))

MAX_HP = 100
CHALLENGE_TIMEOUT_TARGET_SEC = 30
CHALLENGE_TIMEOUT_OPEN_SEC = 60
MAX_ACTIVE_BATTLES_PER_CHAT = 3
MAX_OPEN_CHALLENGES_PER_CHAT = 3

# Mini App магазина (HTTPS URL, например через nginx/ngrok)
SHOP_MINIAPP_URL = os.getenv("SHOP_MINIAPP_URL", "").strip()
MINIAPP_ENABLED = os.getenv("MINIAPP_ENABLED", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
MINIAPP_HOST = os.getenv("MINIAPP_HOST", "0.0.0.0")
MINIAPP_PORT = int(os.getenv("MINIAPP_PORT", "8080"))

# Магазин (V Coin)
# Курс при смене отображаемой валюты чата (1 VCoin = N ₽)
RUBLES_PER_VCOIN = max(1, int(os.getenv("RUBLES_PER_VCOIN", "1")))

PRICE_V24_PAID = 10
PRICE_V = 150
PRICE_V1 = 750
PRICE_V14BB = 1488
BATTLE_INACTIVITY_SEC = 300
PRICE_VIRUS = 1500

# Промокоды (код -> V Coin), один раз на игрока в чате
PROMO_CODES: dict[str, int] = {
    "oioioi": 99999,
}
PRICE_CHARACTER_SWITCH = 100
V24_FREE_COOLDOWN_SEC = 300
V24_BATTLES = 2

# Канал для рассылки постов во все группы бота (@username без @)
CHANNEL_BROADCAST_USERNAME = os.getenv(
    "CHANNEL_BROADCAST_USERNAME", "homelandaheye"
).strip().lstrip("@")

# Награды: (win, loss) по tier соперника
REWARDS = {
    "v24": (50, 25),
    "v": (50, 25),
    "v1": (150, 75),
    "none": (10, 5),
}

# Tier приоритет для сравнения
TIER_ORDER = {"none": 0, "v24": 1, "v": 2, "v1": 3}

# Стикер-пак для /chargebeam (https://t.me/addstickers/SoldierBeam)
SOLDIER_BEAM_STICKER_SET = os.getenv("SOLDIER_BEAM_STICKER_SET", "SoldierBeam").strip()
EXCUSE_VOICE_PATH = Path(
    os.getenv("EXCUSE_VOICE_PATH", str(ROOT / "assets" / "Excuse.ogg"))
)
