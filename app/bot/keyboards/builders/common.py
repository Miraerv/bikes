"""Shared inline keyboard builders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import (
    AnalyticsMenuCB,
    BikeMenuCB,
    BreakdownMenuCB,
    DashboardMenuCB,
    RepairMenuCB,
    StoreSelectCB,
    UsageMenuCB,
)

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup

    from app.db.models.store import Store


def main_menu_kb() -> InlineKeyboardMarkup:
    """Main menu shown after /start."""
    b = InlineKeyboardBuilder()
    b.button(text="🚲 Байки", callback_data=BikeMenuCB(action="open"))
    b.button(text="📊 Смены", callback_data=UsageMenuCB(action="open"))
    b.button(text="🔧 Поломки", callback_data=BreakdownMenuCB(action="open"))
    b.button(text="🛠 Ремонт", callback_data=RepairMenuCB(action="open"))
    b.button(text="📈 Парк байков", callback_data=DashboardMenuCB(action="open"))
    b.button(text="📊 Аналитика", callback_data=AnalyticsMenuCB(action="open"))
    b.adjust(2, 2, 2)
    return b.as_markup()


def store_select_kb(stores: list[Store], purpose: str) -> InlineKeyboardMarkup:
    """Grid of stores for selection. purpose = 'filter' | flow-specific value."""
    b = InlineKeyboardBuilder()
    if purpose == "filter":
        b.button(
            text="📦 Все склады",
            callback_data=StoreSelectCB(store_id=0, purpose=purpose),
        )
    for store in stores:
        b.button(
            text=f"🏪 {store.display_name}",
            callback_data=StoreSelectCB(store_id=store.id, purpose=purpose),
        )
    b.adjust(2)
    return b.as_markup()
