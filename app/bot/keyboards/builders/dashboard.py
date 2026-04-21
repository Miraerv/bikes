"""Inline keyboard builders for dashboard flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import DashboardMenuCB, DashboardStoreCB

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup

    from app.db.models.store import Store


def dashboard_stores_kb(
    stores: list[tuple[Store, dict[str, int]]],
) -> InlineKeyboardMarkup:
    """List of stores with bike counts for dashboard drill-down."""
    b = InlineKeyboardBuilder()
    for store, counts in stores:
        total = sum(counts.values())
        online = counts.get("online", 0)
        repair = counts.get("repair", 0) + counts.get("inspection", 0)
        b.button(
            text=f"🏪 {store.display_name}  ({online}✅ / {repair}🔧 / {total})",
            callback_data=DashboardStoreCB(store_id=store.id),
        )
    b.button(text="← Назад", callback_data=DashboardMenuCB(action="back"))
    rows = [1] * len(stores) + [1]
    b.adjust(*rows)
    return b.as_markup()


def dashboard_back_kb() -> InlineKeyboardMarkup:
    """Back button from store detail to dashboard."""
    b = InlineKeyboardBuilder()
    b.button(text="← Назад к дашборду", callback_data=DashboardMenuCB(action="open"))
    b.adjust(1)
    return b.as_markup()
