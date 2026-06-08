"""Товары магазина (id и подписи)."""

from __future__ import annotations

from game.config import PRICE_V, PRICE_V1, PRICE_V14BB, PRICE_V24_PAID, PRICE_VIRUS

SHOP_ITEMS: list[tuple[str, str]] = [
    ("v24_free", "V24 бесплатно (5м)"),
    ("v24_paid", f"V24 ({PRICE_V24_PAID} coin)"),
    ("v", f"V ({PRICE_V} coin)"),
    ("v1", f"V1 ({PRICE_V1} coin)"),
    ("v14bb", f"V14BB ({PRICE_V14BB} coin)"),
    ("virus", f"Вирус ({PRICE_VIRUS})"),
]

SHOP_ITEM_IDS: list[str] = [item_id for item_id, _ in SHOP_ITEMS]


def shop_item_label(item_id: str) -> str:
    for iid, label in SHOP_ITEMS:
        if iid == item_id:
            return label
    return item_id
