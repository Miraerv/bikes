"""BIKE-23 — Change bike status handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from loguru import logger
from sqlalchemy import select

from app.bot.keyboards.builders import (
    STATUS_EMOJI,
    STATUS_LABEL,
    bike_card_kb,
    bike_status_select_kb,
)
from app.bot.keyboards.callbacks import BikeStatusCB
from app.db.models.bike import Bike, BikeStatus

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="change_status")


@router.callback_query(BikeStatusCB.filter(F.status == "pick"))
async def show_status_options(
    callback: CallbackQuery,
    callback_data: BikeStatusCB,
) -> None:
    """Show available statuses for the bike."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔄 <b>Выберите новый статус:</b>",
        reply_markup=bike_status_select_kb(callback_data.bike_id),
    )


@router.callback_query(BikeStatusCB.filter(F.status != "pick"))
async def set_bike_status(
    callback: CallbackQuery,
    callback_data: BikeStatusCB,
    market_session: AsyncSession,
) -> None:
    """Update bike status in the database."""
    await callback.answer()

    result = await market_session.execute(
        select(Bike).where(Bike.id == callback_data.bike_id),
    )
    bike = result.scalar_one_or_none()

    if bike is None:
        await callback.message.edit_text("⚠️ Байк не найден.")  # type: ignore[union-attr]
        return

    new_status = BikeStatus(callback_data.status)
    old_status = bike.status
    bike.status = new_status

    old_emoji = STATUS_EMOJI.get(old_status.value, "❓")
    old_label = STATUS_LABEL.get(old_status.value, old_status.value)
    new_emoji = STATUS_EMOJI.get(new_status.value, "❓")
    new_label = STATUS_LABEL.get(new_status.value, new_status.value)

    logger.info(
        "Bike {number} status changed: {old} → {new}",
        number=bike.bike_number,
        old=old_status.value,
        new=new_status.value,
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Статус байка <b>{bike.bike_number}</b> изменён\n\n"
        f"{old_emoji} {old_label} → {new_emoji} {new_label}",
        reply_markup=bike_card_kb(bike.id),
    )
