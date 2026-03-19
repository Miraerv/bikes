"""Stage 3 — Usage log handlers (BIKE-30, BIKE-31, BIKE-33)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from aiogram import F, Router
from loguru import logger
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.bot.keyboards.builders import (
    main_menu_kb,
    store_select_kb,
    usage_active_logs_kb,
    usage_bike_select_kb,
    usage_confirm_take_kb,
    usage_courier_select_kb,
    usage_menu_kb,
    usage_return_confirm_kb,
)
from app.bot.keyboards.callbacks import (
    StoreSelectCB,
    UsageActiveStoreCB,
    UsageBikeSelectCB,
    UsageConfirmCB,
    UsageCourierSelectCB,
    UsageMenuCB,
    UsageReturnBikeCB,
    UsageReturnConfirmCB,
)
from app.bot.states.bike import TakeBikeForm
from app.core.config import settings
from app.core.tz import now_display, to_yakutsk
from app.db.models.admin_user import AdminUser
from app.db.models.bike import Bike, BikeStatus
from app.db.models.bike_usage_log import BikeUsageLog
from app.db.models.store import Store

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="usage")


# ── Usage sub-menu ──────────────────────────────────────────────────────


@router.callback_query(UsageMenuCB.filter(F.action == "open"))
async def open_usage_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show usage sub-menu (take / return / active)."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "📊 <b>Управление сменами</b>\n\nВыберите действие:",
        reply_markup=usage_menu_kb(),
    )


@router.callback_query(UsageMenuCB.filter(F.action == "back"))
async def back_to_main(callback: CallbackQuery) -> None:
    """Return to main menu."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  BIKE-30 — Взял байк (Take bike)
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(UsageMenuCB.filter(F.action == "take"))
async def take_choose_store(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Step 1: Choose store."""
    await callback.answer()

    result = await market_session.execute(
        select(Store)
            .where(Store.main_id == "express", Store.id.notin_(settings.hidden_store_ids))
            .order_by(Store.street),
    )
    stores = list(result.scalars().all())

    if not stores:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Нет доступных складов.",
            reply_markup=usage_menu_kb(),
        )
        return

    await state.set_state(TakeBikeForm.store)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚴 <b>Взял байк</b>\n\nВыберите склад:",
        reply_markup=store_select_kb(stores, purpose="usage_take"),
    )


@router.callback_query(
    TakeBikeForm.store,
    StoreSelectCB.filter(F.purpose == "usage_take"),
)
async def take_choose_bike(
    callback: CallbackQuery,
    callback_data: StoreSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Step 2: Choose bike (only online bikes at the store)."""
    await callback.answer()
    store_id = callback_data.store_id

    result = await market_session.execute(
        select(Bike)
        .where(Bike.store_id == store_id, Bike.status == BikeStatus.ONLINE)
        .order_by(Bike.bike_number),
    )
    bikes = list(result.scalars().all())

    if not bikes:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 Нет свободных байков на этом складе.",
            reply_markup=usage_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(store_id=store_id)
    await state.set_state(TakeBikeForm.bike)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚲 Выберите <b>байк</b>:",
        reply_markup=usage_bike_select_kb(bikes, store_id),
    )

@router.callback_query(TakeBikeForm.bike, UsageBikeSelectCB.filter())
async def take_prompt_courier_search(
    callback: CallbackQuery,
    callback_data: UsageBikeSelectCB,
    state: FSMContext,
) -> None:
    """Step 3: Prompt supervisor to type courier name for search."""
    await callback.answer()

    await state.update_data(
        bike_id=callback_data.bike_id,
        store_id=callback_data.store_id,
    )
    await state.set_state(TakeBikeForm.courier_search)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔍 <b>Поиск курьера</b>\n\n"
        "Введите имя или фамилию курьера:",
    )


@router.message(TakeBikeForm.courier_search, F.text)
async def take_courier_search(
    message: Message,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Step 3b: Search couriers by name/surname and show results."""
    query_text = message.text.strip()
    data = await state.get_data()

    pattern = f"%{query_text}%"
    result = await market_session.execute(
        select(AdminUser)
        .where(
            or_(
                AdminUser.name.ilike(pattern),
                AdminUser.surname.ilike(pattern),
            ),
        )
        .order_by(AdminUser.name)
        .limit(20),
    )
    couriers = list(result.scalars().all())

    if not couriers:
        await message.answer(
            f"⚠️ По запросу «<b>{query_text}</b>» никого не найдено.\n\n"
            "Попробуйте ещё раз — введите имя или фамилию:",
        )
        return

    await state.set_state(TakeBikeForm.courier)
    await message.answer(
        f"👤 Найдено: <b>{len(couriers)}</b>\n\n"
        "Выберите курьера:",
        reply_markup=usage_courier_select_kb(
            couriers, data["bike_id"], data["store_id"],
        ),
    )


@router.callback_query(TakeBikeForm.courier, UsageCourierSelectCB.filter())
async def take_confirm(
    callback: CallbackQuery,
    callback_data: UsageCourierSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Step 4: Show confirmation."""
    await callback.answer()
    await state.update_data(courier_id=callback_data.courier_id)

    # Fetch names for display
    bike = await market_session.get(Bike, callback_data.bike_id)
    courier = await market_session.get(AdminUser, callback_data.courier_id)
    store_result = await market_session.execute(
        select(Store).where(Store.id == callback_data.store_id),
    )
    store = store_result.scalar_one_or_none()

    bike_label = f"{bike.bike_number} — {bike.model}" if bike else "—"
    courier_label = courier.display_name if courier else "—"
    store_label = store.display_name if store else "—"

    await state.update_data(
        bike_label=bike_label,
        courier_label=courier_label,
        store_label=store_label,
    )
    await state.set_state(TakeBikeForm.confirm)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "📋 <b>Подтвердите взятие байка:</b>\n\n"
        f"🚲 Байк: <b>{bike_label}</b>\n"
        f"👤 Курьер: <b>{courier_label}</b>\n"
        f"🏪 Склад: <b>{store_label}</b>\n\n"
        "Всё верно?",
        reply_markup=usage_confirm_take_kb(),
    )


@router.callback_query(TakeBikeForm.confirm, UsageConfirmCB.filter(F.action == "save"))
async def take_save(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Create the usage log record."""
    await callback.answer()
    data = await state.get_data()

    log = BikeUsageLog(
        bike_id=data["bike_id"],
        courier_id=data["courier_id"],
        store_id=data["store_id"],
        started_at=datetime.now(),
    )
    market_session.add(log)
    await market_session.flush()

    logger.info(
        "Usage log created: bike={bike}, courier={courier}, store={store}",
        bike=data.get("bike_label"),
        courier=data.get("courier_label"),
        store=data.get("store_label"),
    )

    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ Смена начата!\n\n"
        f"🚲 {data['bike_label']}\n"
        f"👤 {data['courier_label']}\n"
        f"🏪 {data['store_label']}\n"
        f"🕐 {now_display().strftime('%H:%M')}",
        reply_markup=usage_menu_kb(),
    )


@router.callback_query(TakeBikeForm.confirm, UsageConfirmCB.filter(F.action == "cancel"))
async def take_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel taking a bike."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "❌ Взятие байка отменено.",
        reply_markup=usage_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  BIKE-31 — Вернул байк (Return bike)
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(UsageMenuCB.filter(F.action == "return"))
async def return_choose_store(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Show stores that have active shifts."""
    await callback.answer()

    result = await market_session.execute(
        select(Store)
            .where(Store.main_id == "express", Store.id.notin_(settings.hidden_store_ids))
            .order_by(Store.street),
    )
    stores = list(result.scalars().all())

    if not stores:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Нет доступных складов.",
            reply_markup=usage_menu_kb(),
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔙 <b>Вернул байк</b>\n\nВыберите склад:",
        reply_markup=store_select_kb(stores, purpose="usage_return"),
    )


@router.callback_query(StoreSelectCB.filter(F.purpose == "usage_return"))
async def return_show_active_logs(
    callback: CallbackQuery,
    callback_data: StoreSelectCB,
    market_session: AsyncSession,
) -> None:
    """Show active shifts at the selected store."""
    await callback.answer()

    query = (
        select(BikeUsageLog)
        .options(
            selectinload(BikeUsageLog.bike),
            selectinload(BikeUsageLog.courier),
        )
        .where(BikeUsageLog.ended_at.is_(None))
        .order_by(BikeUsageLog.started_at.desc())
    )
    if callback_data.store_id > 0:
        query = query.where(BikeUsageLog.store_id == callback_data.store_id)

    result = await market_session.execute(query)
    logs = list(result.scalars().all())

    if not logs:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 Нет активных смен на этом складе.",
            reply_markup=usage_menu_kb(),
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔙 Выберите смену для возврата:",
        reply_markup=usage_active_logs_kb(logs),
    )


@router.callback_query(UsageReturnBikeCB.filter())
async def return_confirm(
    callback: CallbackQuery,
    callback_data: UsageReturnBikeCB,
    market_session: AsyncSession,
) -> None:
    """Ask for confirmation before ending the shift."""
    await callback.answer()

    result = await market_session.execute(
        select(BikeUsageLog)
        .options(
            selectinload(BikeUsageLog.bike),
            selectinload(BikeUsageLog.courier),
            selectinload(BikeUsageLog.store),
        )
        .where(BikeUsageLog.id == callback_data.log_id),
    )
    log = result.scalar_one_or_none()

    if log is None or log.ended_at is not None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Смена не найдена или уже завершена.",
            reply_markup=usage_menu_kb(),
        )
        return

    courier_name = log.courier.display_name if log.courier else "—"
    bike_num = log.bike.bike_number if log.bike else "—"
    bike_model = log.bike.model if log.bike else ""
    store_name = log.store.display_name if log.store else "—"
    started = to_yakutsk(log.started_at).strftime("%d.%m %H:%M")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "⚠️ <b>Завершить смену?</b>\n\n"
        f"🚲 {bike_num} — {bike_model}\n"
        f"👤 {courier_name}\n"
        f"🏪 {store_name}\n"
        f"🕐 Начало: {started}",
        reply_markup=usage_return_confirm_kb(log.id),
    )


@router.callback_query(UsageReturnConfirmCB.filter(F.confirm == True))  # noqa: E712
async def return_save(
    callback: CallbackQuery,
    callback_data: UsageReturnConfirmCB,
    market_session: AsyncSession,
) -> None:
    """End the shift — set ended_at = now."""
    await callback.answer()

    result = await market_session.execute(
        select(BikeUsageLog)
        .options(
            selectinload(BikeUsageLog.bike),
            selectinload(BikeUsageLog.courier),
        )
        .where(BikeUsageLog.id == callback_data.log_id),
    )
    log = result.scalar_one_or_none()

    if log is None or log.ended_at is not None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Смена не найдена или уже завершена.",
            reply_markup=usage_menu_kb(),
        )
        return

    log.ended_at = datetime.now()

    courier_name = log.courier.display_name if log.courier else "—"
    bike_num = log.bike.bike_number if log.bike else "—"

    logger.info(
        "Usage log ended: log_id={log_id}, bike={bike}, courier={courier}",
        log_id=log.id,
        bike=bike_num,
        courier=courier_name,
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ Смена завершена!\n\n"
        f"🚲 {bike_num}\n"
        f"👤 {courier_name}\n"
        f"🕐 {to_yakutsk(log.started_at).strftime('%H:%M')}"
        f" → {to_yakutsk(log.ended_at).strftime('%H:%M')}",
        reply_markup=usage_menu_kb(),
    )


@router.callback_query(UsageReturnConfirmCB.filter(F.confirm == False))  # noqa: E712
async def return_cancel(callback: CallbackQuery) -> None:
    """Cancel returning a bike."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "❌ Возврат отменён.",
        reply_markup=usage_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  BIKE-33 — Кто сейчас на байке (Active shifts)
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(UsageMenuCB.filter(F.action == "active"))
async def active_choose_store(
    callback: CallbackQuery,
    market_session: AsyncSession,
) -> None:
    """Choose store to see active shifts."""
    await callback.answer()

    result = await market_session.execute(
        select(Store)
            .where(Store.main_id == "express", Store.id.notin_(settings.hidden_store_ids))
            .order_by(Store.street),
    )
    stores = list(result.scalars().all())

    from aiogram.utils.keyboard import InlineKeyboardBuilder

    b = InlineKeyboardBuilder()
    b.button(
        text="📦 Все склады",
        callback_data=UsageActiveStoreCB(store_id=0),
    )
    for store in stores:
        b.button(
            text=f"🏪 {store.display_name}",
            callback_data=UsageActiveStoreCB(store_id=store.id),
        )
    b.button(text="← Назад", callback_data=UsageMenuCB(action="open"))
    b.adjust(2)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "👀 <b>Кто на байке</b>\n\nВыберите склад:",
        reply_markup=b.as_markup(),
    )


@router.callback_query(UsageActiveStoreCB.filter())
async def active_show_shifts(
    callback: CallbackQuery,
    callback_data: UsageActiveStoreCB,
    market_session: AsyncSession,
) -> None:
    """Show all active shifts at the selected store."""
    await callback.answer()

    query = (
        select(BikeUsageLog)
        .options(
            selectinload(BikeUsageLog.bike),
            selectinload(BikeUsageLog.courier),
            selectinload(BikeUsageLog.store),
        )
        .where(BikeUsageLog.ended_at.is_(None))
        .order_by(BikeUsageLog.started_at.desc())
    )
    if callback_data.store_id > 0:
        query = query.where(BikeUsageLog.store_id == callback_data.store_id)

    result = await market_session.execute(query)
    logs = list(result.scalars().all())

    if not logs:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 Нет активных смен.",
            reply_markup=usage_menu_kb(),
        )
        return

    lines = ["👀 <b>Активные смены</b>", f"Всего: {len(logs)}", ""]

    for log in logs:
        courier_name = log.courier.display_name if log.courier else "—"
        bike_num = log.bike.bike_number if log.bike else "—"
        bike_model = log.bike.model if log.bike else ""
        store_name = log.store.display_name if log.store else "—"
        started = to_yakutsk(log.started_at).strftime("%d.%m %H:%M")
        lines.append(
            f"🚲 <b>{bike_num}</b> {bike_model}\n"
            f"   👤 {courier_name} • 🏪 {store_name}\n"
            f"   🕐 с {started}\n",
        )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=usage_menu_kb(),
    )
