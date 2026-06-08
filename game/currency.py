"""Отображаемая валюта чата (VCoins / Рубли). В БД баланс хранится в единицах VCoins."""

from __future__ import annotations

from game.config import RUBLES_PER_VCOIN

CURRENCY_VCOINS = "vcoins"
CURRENCY_RUBLES = "rubles"

_CURRENCY_ALIASES: dict[str, str] = {
    "vcoins": CURRENCY_VCOINS,
    "vcoin": CURRENCY_VCOINS,
    "vc": CURRENCY_VCOINS,
    "v": CURRENCY_VCOINS,
    "рубли": CURRENCY_RUBLES,
    "рубль": CURRENCY_RUBLES,
    "руб": CURRENCY_RUBLES,
    "rubles": CURRENCY_RUBLES,
    "ruble": CURRENCY_RUBLES,
    "rub": CURRENCY_RUBLES,
    "₽": CURRENCY_RUBLES,
}


def normalize_currency_arg(arg: str) -> str | None:
    key = arg.strip().lower()
    return _CURRENCY_ALIASES.get(key)


def currency_title(currency: str) -> str:
    if currency == CURRENCY_RUBLES:
        return "Рубли"
    return "VCoins"


def to_display_units(chat_currency: str, coins_vcoin: int) -> int:
    """Баланс в VCoins → число для отображения в валюте чата."""
    if chat_currency == CURRENCY_RUBLES:
        return coins_vcoin * RUBLES_PER_VCOIN
    return coins_vcoin


def from_display_units(chat_currency: str, display_units: int) -> int:
    """Сумма из команды (в валюте чата) → списание в VCoins."""
    if chat_currency == CURRENCY_RUBLES:
        if RUBLES_PER_VCOIN <= 0:
            return display_units
        return display_units // RUBLES_PER_VCOIN
    return display_units


def display_amount(chat_currency: str, coins_vcoin: int) -> str:
    shown = to_display_units(chat_currency, coins_vcoin)
    if chat_currency == CURRENCY_RUBLES:
        return f"{shown} ₽"
    return f"{shown} VCoins"


def display_price(chat_currency: str, price_vcoin: int) -> str:
    return display_amount(chat_currency, price_vcoin)
