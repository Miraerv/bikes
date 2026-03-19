"""Stage 11 — Courier shift handler (simplified bike take/return)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loguru import logger
from sqlalchemy import select

from app.bot.keyboards.builders import courier_menu_kb
from app.bot.keyboards.callbacks import (
    CourierBikeSelectCB,
    CourierMenuCB,
    CourierReturnConfirmCB,
    CourierStoreSelectCB,
    CourierTakeConfirmCB,
)
from app.core.config import settings
from app.core.tz import now_display, to_yakutsk
from app.db.models.bike import Bike, BikeStatus
from app.db.models.courier_shift import CourierShift
from app.db.models.courier_shift_bike import CourierShiftBike
from app.db.models.store import Store

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.bot_user import BotUser

router = Router(name="courier_shift")


# ── Helper ─────────────────────────────────────────────────────────────


async def _find_active_shift(
    market_session: AsyncSession,
    admin_user_id: int,
) -> CourierShift | None:
    """Find the active (open) shift for this courier.

    Active = status 'online' AND shift_end IS NULL.
    """
    result = await market_session.execute(
        select(CourierShift)
        .where(
            CourierShift.admin_user_id == admin_user_id,
            CourierShift.status == "online",
            CourierShift.shift_end.is_(None),
        )
        .order_by(CourierShift.shift_start.desc())
        .limit(1),
    )
    return result.scalar_one_or_none()


# ── Courier sub-menu ───────────────────────────────────────────────────


@router.callback_query(CourierMenuCB.filter(F.action == "open"))
async def open_courier_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show courier shift menu."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚚 <b>Меню курьера</b>\n\nВыберите действие:",
        reply_markup=courier_menu_kb(),
    )


@router.callback_query(CourierMenuCB.filter(F.action == "back"))
async def courier_back_to_menu(callback: CallbackQuery) -> None:
    """Return to courier menu."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚚 <b>Меню курьера</b>\n\nВыберите действие:",
        reply_markup=courier_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  Взял байк (Take bike): Store → Bike → Confirm
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(CourierMenuCB.filter(F.action == "take"))
async def take_choose_store(
    callback: CallbackQuery,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Step 1: Check active shift, then show store selection."""
    await callback.answer()

    if not bot_user or not bot_user.admin_user_id:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Ваш аккаунт не привязан к системе.\n"
            "Обратитесь к администратору.",
            reply_markup=courier_menu_kb(),
        )
        return

    # Check for active shift
    shift = await _find_active_shift(market_session, bot_user.admin_user_id)
    if not shift:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ <b>Нет активной смены</b>\n\n"
            "У вас нет открытой смены.\n"
            "Нажмите в шопере «Начать смену».",
            reply_markup=courier_menu_kb(),
        )
        return

    # Show store selection
    result = await market_session.execute(
        select(Store)
            .where(Store.main_id == "express", Store.id.notin_(settings.hidden_store_ids))
            .order_by(Store.street),
    )
    stores = list(result.scalars().all())

    if not stores:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Нет доступных складов.",
            reply_markup=courier_menu_kb(),
        )
        return

    b = InlineKeyboardBuilder()
    for store in stores:
        b.button(
            text=f"🏪 {store.display_name}",
            callback_data=CourierStoreSelectCB(store_id=store.id),
        )
    b.button(text="← Назад", callback_data=CourierMenuCB(action="open"))
    b.adjust(1)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚲 <b>Взял байк</b>\n\nВыберите склад:",
        reply_markup=b.as_markup(),
    )


@router.callback_query(CourierStoreSelectCB.filter())
async def take_choose_bike(
    callback: CallbackQuery,
    callback_data: CourierStoreSelectCB,
    market_session: AsyncSession,
) -> None:
    """Step 2: Show available bikes at the selected store."""
    await callback.answer()
    store_id = callback_data.store_id

    result = await market_session.execute(
        select(Bike)
        .where(
            Bike.store_id == store_id,
            Bike.status == BikeStatus.ONLINE,
        )
        .order_by(Bike.bike_number),
    )
    bikes = list(result.scalars().all())

    if not bikes:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 На этом складе нет доступных байков.",
            reply_markup=courier_menu_kb(),
        )
        return

    b = InlineKeyboardBuilder()
    for bike in bikes:
        b.button(
            text=f"🚲 {bike.bike_number} — {bike.model}",
            callback_data=CourierBikeSelectCB(bike_id=bike.id),
        )
    b.button(text="← Назад", callback_data=CourierMenuCB(action="take"))
    b.adjust(1)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚲 <b>Выберите байк:</b>",
        reply_markup=b.as_markup(),
    )


@router.callback_query(CourierBikeSelectCB.filter())
async def take_confirm(
    callback: CallbackQuery,
    callback_data: CourierBikeSelectCB,
    market_session: AsyncSession,
) -> None:
    """Step 3: Show confirmation for selected bike."""
    await callback.answer()
    bike_id = callback_data.bike_id

    bike = await market_session.get(Bike, bike_id)
    if not bike:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Байк не найден.",
            reply_markup=courier_menu_kb(),
        )
        return

    b = InlineKeyboardBuilder()
    b.button(
        text="✅ Подтвердить",
        callback_data=CourierTakeConfirmCB(bike_id=bike.id, action="save"),
    )
    b.button(
        text="❌ Отмена",
        callback_data=CourierTakeConfirmCB(bike_id=bike.id, action="cancel"),
    )
    b.adjust(2)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "📋 <b>Подтвердите взятие байка:</b>\n\n"
        f"🚲 Номер: <b>{bike.bike_number}</b>\n"
        f"🏍 Модель: <b>{bike.model}</b>\n\n"
        "Всё верно?",
        reply_markup=b.as_markup(),
    )


@router.callback_query(CourierTakeConfirmCB.filter(F.action == "save"))
async def take_save(
    callback: CallbackQuery,
    callback_data: CourierTakeConfirmCB,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Save the bike take record to boom_shift_couriers_bike."""
    await callback.answer()

    if not bot_user or not bot_user.admin_user_id:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Ошибка авторизации.",
            reply_markup=courier_menu_kb(),
        )
        return

    bike = await market_session.get(Bike, callback_data.bike_id)
    if not bike:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Байк не найден.",
            reply_markup=courier_menu_kb(),
        )
        return

    shift = await _find_active_shift(market_session, bot_user.admin_user_id)
    if not shift:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Нет активной смены.",
            reply_markup=courier_menu_kb(),
        )
        return

    record = CourierShiftBike(
        shift_id=shift.id,
        bike_number=bike.bike_number,
        type="start",
        photo_url="",
        checklist="{}",
    )
    market_session.add(record)
    await market_session.flush()

    logger.info(
        "Courier took bike: shift_id={shift}, bike={bike}",
        shift=shift.id,
        bike=bike.bike_number,
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ <b>Байк взят!</b>\n\n"
        f"🚲 {bike.bike_number} — {bike.model}\n"
        f"🕐 {now_display().strftime('%H:%M')}",
        reply_markup=courier_menu_kb(),
    )


@router.callback_query(CourierTakeConfirmCB.filter(F.action == "cancel"))
async def take_cancel(callback: CallbackQuery) -> None:
    """Cancel taking a bike."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "❌ Взятие байка отменено.",
        reply_markup=courier_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  Вернул байк (Return bike)
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(CourierMenuCB.filter(F.action == "return"))
async def return_start(
    callback: CallbackQuery,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Show active bike records for return."""
    await callback.answer()

    if not bot_user or not bot_user.admin_user_id:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Ваш аккаунт не привязан к системе.",
            reply_markup=courier_menu_kb(),
        )
        return

    # Find active shift
    shift = await _find_active_shift(market_session, bot_user.admin_user_id)
    if not shift:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 Нет активной смены.",
            reply_markup=courier_menu_kb(),
        )
        return

    # Find start records without matching end records
    start_records = await market_session.execute(
        select(CourierShiftBike)
        .where(
            CourierShiftBike.shift_id == shift.id,
            CourierShiftBike.type == "start",
        )
        .order_by(CourierShiftBike.created_at.desc()),
    )
    starts = list(start_records.scalars().all())

    # Find end records for this shift
    end_records = await market_session.execute(
        select(CourierShiftBike.bike_number)
        .where(
            CourierShiftBike.shift_id == shift.id,
            CourierShiftBike.type == "end",
        ),
    )
    returned_bikes = {row[0] for row in end_records.all()}

    # Filter: bikes that have been taken but not returned
    active_bikes = [s for s in starts if s.bike_number not in returned_bikes]

    if not active_bikes:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 У вас нет взятых байков.",
            reply_markup=courier_menu_kb(),
        )
        return

    # Build keyboard with active bikes
    b = InlineKeyboardBuilder()
    for record in active_bikes:
        taken_at = to_yakutsk(record.created_at).strftime("%H:%M")
        b.button(
            text=f"🔙 {record.bike_number} (с {taken_at})",
            callback_data=CourierReturnConfirmCB(
                shift_bike_id=record.id, confirm=False,
            ),
        )
    b.button(text="← Назад", callback_data=CourierMenuCB(action="open"))
    b.adjust(1)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔙 <b>Вернуть байк</b>\n\nВыберите байк:",
        reply_markup=b.as_markup(),
    )


@router.callback_query(CourierReturnConfirmCB.filter(F.confirm == False))  # noqa: E712
async def return_confirm(
    callback: CallbackQuery,
    callback_data: CourierReturnConfirmCB,
    market_session: AsyncSession,
) -> None:
    """Show confirmation before returning bike."""
    await callback.answer()

    record = await market_session.get(CourierShiftBike, callback_data.shift_bike_id)
    if not record:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Запись не найдена.",
            reply_markup=courier_menu_kb(),
        )
        return

    taken_at = to_yakutsk(record.created_at).strftime("%d.%m %H:%M")

    b = InlineKeyboardBuilder()
    b.button(
        text="✅ Да, вернул",
        callback_data=CourierReturnConfirmCB(
            shift_bike_id=record.id, confirm=True,
        ),
    )
    b.button(text="❌ Отмена", callback_data=CourierMenuCB(action="open"))
    b.adjust(2)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "⚠️ <b>Вернуть байк?</b>\n\n"
        f"🚲 Номер: <b>{record.bike_number}</b>\n"
        f"🕐 Взят: {taken_at}",
        reply_markup=b.as_markup(),
    )


@router.callback_query(CourierReturnConfirmCB.filter(F.confirm == True))  # noqa: E712
async def return_save(
    callback: CallbackQuery,
    callback_data: CourierReturnConfirmCB,
    market_session: AsyncSession,
) -> None:
    """Create end record for the bike."""
    await callback.answer()

    start_record = await market_session.get(
        CourierShiftBike, callback_data.shift_bike_id,
    )
    if not start_record:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Запись не найдена.",
            reply_markup=courier_menu_kb(),
        )
        return

    # Create end record
    end_record = CourierShiftBike(
        shift_id=start_record.shift_id,
        bike_number=start_record.bike_number,
        type="end",
        photo_url="",
        checklist="{}",
    )
    market_session.add(end_record)

    logger.info(
        "Courier returned bike: shift_id={shift}, bike={bike}",
        shift=start_record.shift_id,
        bike=start_record.bike_number,
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ <b>Байк возвращён!</b>\n\n"
        f"🚲 Номер: <b>{start_record.bike_number}</b>\n"
        f"🕐 {now_display().strftime('%H:%M')}",
        reply_markup=courier_menu_kb(),
    )
