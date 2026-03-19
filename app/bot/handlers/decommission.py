"""BIKE-24 — Decommission bike handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from loguru import logger
from sqlalchemy import select

from app.bot.keyboards.builders import bike_menu_kb, confirm_decommission_kb
from app.bot.keyboards.callbacks import BikeDecommissionCB
from app.db.models.bike import Bike, BikeStatus

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="decommission")


@router.callback_query(BikeDecommissionCB.filter(F.confirm == False))  # noqa: E712
async def ask_decommission(
    callback: CallbackQuery,
    callback_data: BikeDecommissionCB,
    market_session: AsyncSession,
) -> None:
    """Ask for confirmation before decommissioning."""
    await callback.answer()

    result = await market_session.execute(
        select(Bike).where(Bike.id == callback_data.bike_id),
    )
    bike = result.scalar_one_or_none()

    if bike is None:
        await callback.message.edit_text("⚠️ Байк не найден.")  # type: ignore[union-attr]
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"⚠️ <b>Списать байк {bike.bike_number}?</b>\n\n"
        f"🏍 {bike.model}\n"
        "Это действие изменит статус байка на ⚫ Списан.\n\n"
        "Вы уверены?",
        reply_markup=confirm_decommission_kb(bike.id),
    )


@router.callback_query(BikeDecommissionCB.filter(F.confirm == True))  # noqa: E712
async def confirm_decommission(
    callback: CallbackQuery,
    callback_data: BikeDecommissionCB,
    market_session: AsyncSession,
) -> None:
    """Decommission the bike (set status to decommissioned)."""
    await callback.answer()

    result = await market_session.execute(
        select(Bike).where(Bike.id == callback_data.bike_id),
    )
    bike = result.scalar_one_or_none()

    if bike is None:
        await callback.message.edit_text("⚠️ Байк не найден.")  # type: ignore[union-attr]
        return

    bike.status = BikeStatus.DECOMMISSIONED

    logger.info("Bike {number} decommissioned", number=bike.bike_number)

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"⚫ Байк <b>{bike.bike_number}</b> списан.\n\n"
        f"🏍 {bike.model}",
        reply_markup=bike_menu_kb(),
    )
