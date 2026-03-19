"""BIKE-22 — Bike card handler (detailed info + history)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.keyboards.builders import (
    STATUS_EMOJI,
    STATUS_LABEL,
    bike_card_actions_kb,
    bike_menu_kb,
)
from app.bot.keyboards.callbacks import BikeCardCB
from app.core.tz import to_yakutsk
from app.db.models.bike import Bike
from app.db.models.bike_breakdown import BikeBreakdown
from app.db.models.bike_usage_log import BikeUsageLog

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="bike_card")


@router.callback_query(BikeCardCB.filter())
async def show_bike_card(
    callback: CallbackQuery,
    callback_data: BikeCardCB,
    market_session: AsyncSession,
) -> None:
    """Show full bike card with recent usage and breakdown stats."""
    await callback.answer()

    # Load bike with store
    result = await market_session.execute(
        select(Bike)
        .options(selectinload(Bike.store))
        .where(Bike.id == callback_data.bike_id),
    )
    bike = result.scalar_one_or_none()

    if bike is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Байк не найден.",
            reply_markup=bike_menu_kb(),
        )
        return

    # Status info
    emoji = STATUS_EMOJI.get(bike.status.value, "❓")
    label = STATUS_LABEL.get(bike.status.value, bike.status.value)
    store_name = bike.store.display_name if bike.store else "—"

    # Last 3 usage logs
    usage_result = await market_session.execute(
        select(BikeUsageLog)
        .options(selectinload(BikeUsageLog.courier))
        .where(BikeUsageLog.bike_id == bike.id)
        .order_by(BikeUsageLog.started_at.desc())
        .limit(3),
    )
    recent_usages = usage_result.scalars().all()

    # Breakdown count
    bd_count_result = await market_session.execute(
        select(BikeBreakdown.id).where(BikeBreakdown.bike_id == bike.id),
    )
    breakdown_count = len(bd_count_result.all())

    # Build card text
    lines = [
        f"🚲 <b>Карточка байка #{bike.bike_number}</b>",
        "",
        f"🏍 Модель: <b>{bike.model}</b>",
        f"🏪 Склад: <b>{store_name}</b>",
        f"📊 Статус: {emoji} <b>{label}</b>",
        f"📅 Эксплуатация с: <b>{bike.commissioned_at.strftime('%d.%m.%Y')}</b>",
        f"🔧 Поломок: <b>{breakdown_count}</b>",
    ]

    if recent_usages:
        lines.append("")
        lines.append("📝 <b>Последние использования:</b>")
        for log in recent_usages:
            courier_name = log.courier.display_name if log.courier else "—"
            started = to_yakutsk(log.started_at).strftime("%d.%m %H:%M")
            status_text = "🔄 На смене" if log.ended_at is None else "✅ Завершено"
            lines.append(f"  • {courier_name} — {started} {status_text}")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=bike_card_actions_kb(bike.id),
    )
