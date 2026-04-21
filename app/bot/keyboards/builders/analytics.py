"""Inline keyboard builders for analytics flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.keyboards.callbacks import AnalyticsMenuCB

if TYPE_CHECKING:
    from aiogram.types import InlineKeyboardMarkup


def analytics_menu_kb() -> InlineKeyboardMarkup:
    """Sub-menu: analytics reports."""
    b = InlineKeyboardBuilder()
    b.button(
        text="📋 Поломки за месяц",
        callback_data=AnalyticsMenuCB(action="breakdowns_month"),
    )
    b.button(
        text="👤 Поломки по курьерам",
        callback_data=AnalyticsMenuCB(action="breakdowns_couriers"),
    )
    b.button(
        text="🔴 Ненадёжные байки",
        callback_data=AnalyticsMenuCB(action="unreliable_bikes"),
    )
    b.button(
        text="🛠 Ремонты",
        callback_data=AnalyticsMenuCB(action="bike_repairs"),
    )
    b.button(
        text="⏱ Даунтайм",
        callback_data=AnalyticsMenuCB(action="downtime"),
    )
    b.button(
        text="✅ Аккуратные курьеры",
        callback_data=AnalyticsMenuCB(action="careful_couriers"),
    )
    b.button(text="← Назад", callback_data=AnalyticsMenuCB(action="back"))
    b.adjust(2, 2, 2, 1)
    return b.as_markup()


def analytics_back_kb() -> InlineKeyboardMarkup:
    """Back button from report to analytics menu."""
    b = InlineKeyboardBuilder()
    b.button(text="← Назад к аналитике", callback_data=AnalyticsMenuCB(action="open"))
    b.adjust(1)
    return b.as_markup()
