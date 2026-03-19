"""BIKE-20 — Add bike handler (FSM multi-step flow)."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.filters import Command
from loguru import logger
from sqlalchemy import select

from app.bot.keyboards.builders import (
    STATUS_EMOJI,
    STATUS_LABEL,
    add_bike_confirm_kb,
    bike_menu_kb,
    store_select_kb,
)
from app.bot.keyboards.callbacks import AddBikeConfirmCB, BikeMenuCB, StoreSelectCB
from app.bot.states.bike import AddBikeForm
from app.core.config import settings
from app.core.tz import now_display
from app.db.models.bike import Bike
from app.db.models.store import Store

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="add_bike")

DATE_FORMAT = "%d.%m.%Y"


# ── Cancel command (MUST be registered BEFORE FSM state handlers) ───────


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    """Cancel any active FSM state."""
    current = await state.get_state()
    if current is None:
        await message.answer("🤷 Нечего отменять.")
        return

    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=bike_menu_kb(),
    )


# ── Entry point ─────────────────────────────────────────────────────────


@router.callback_query(BikeMenuCB.filter(F.action == "add"))
async def start_add_bike(callback: CallbackQuery, state: FSMContext) -> None:
    """Begin the add-bike FSM flow."""
    await callback.answer()
    await state.set_state(AddBikeForm.bike_number)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚲 <b>Добавление байка</b>\n\n"
        "Введите <b>номер байка</b> (наклейка/маркировка):\n\n"
        "<i>Для отмены введите /cancel</i>",
    )


# ── Step 1: Bike number ────────────────────────────────────────────────


@router.message(AddBikeForm.bike_number, F.text, ~Command("cancel"))
async def process_bike_number(
    message: Message,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Validate and save bike number, ask for model."""
    bike_number = message.text.strip()  # type: ignore[union-attr]

    # Check uniqueness
    existing = await market_session.execute(
        select(Bike).where(Bike.bike_number == bike_number),
    )
    if existing.scalar_one_or_none() is not None:
        await message.answer(
            f"⚠️ Байк с номером <b>{bike_number}</b> уже существует.\n"
            "Введите другой номер:",
        )
        return

    await state.update_data(bike_number=bike_number)
    await state.set_state(AddBikeForm.model)
    await message.answer(
        f"✅ Номер: <b>{bike_number}</b>\n\n"
        "Введите <b>модель</b> байка (например, Kugoo M4 Pro):",
    )


# ── Step 2: Model ──────────────────────────────────────────────────────


@router.message(AddBikeForm.model, F.text, ~Command("cancel"))
async def process_model(
    message: Message,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Save model, show store selection."""
    model_name = message.text.strip()  # type: ignore[union-attr]
    await state.update_data(model=model_name)

    # Load stores from market DB
    result = await market_session.execute(
        select(Store)
            .where(Store.main_id == "express", Store.id.notin_(settings.hidden_store_ids))
            .order_by(Store.street),
    )
    stores = list(result.scalars().all())

    if not stores:
        await message.answer("⚠️ Нет доступных складов. Обратитесь к администратору.")
        await state.clear()
        return

    await state.set_state(AddBikeForm.store)
    await message.answer(
        f"✅ Модель: <b>{model_name}</b>\n\n"
        "Выберите <b>склад</b>:",
        reply_markup=store_select_kb(stores, purpose="add"),
    )


# ── Step 3: Store selection ─────────────────────────────────────────────


@router.callback_query(AddBikeForm.store, StoreSelectCB.filter(F.purpose == "add"))
async def process_store(
    callback: CallbackQuery,
    callback_data: StoreSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Save store, ask for commissioning date."""
    await callback.answer()

    store_id = callback_data.store_id
    result = await market_session.execute(select(Store).where(Store.id == store_id))
    store = result.scalar_one_or_none()

    if store is None:
        await callback.message.edit_text("⚠️ Склад не найден.")  # type: ignore[union-attr]
        await state.clear()
        return

    await state.update_data(store_id=store_id, store_name=store.display_name)
    await state.set_state(AddBikeForm.commissioned_at)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Склад: <b>{store.display_name}</b>\n\n"
        "Введите <b>дату ввода в эксплуатацию</b> (ДД.ММ.ГГГГ):\n"
        f"<i>Например: {now_display().strftime(DATE_FORMAT)}</i>",
    )


# ── Step 4: Commissioning date ──────────────────────────────────────────


@router.message(AddBikeForm.commissioned_at, F.text, ~Command("cancel"))
async def process_date(message: Message, state: FSMContext) -> None:
    """Parse date, show confirmation summary."""
    raw = message.text.strip()  # type: ignore[union-attr]
    try:
        parsed = datetime.strptime(raw, DATE_FORMAT).date()
    except ValueError:
        await message.answer(
            "⚠️ Неверный формат даты. Введите в формате <b>ДД.ММ.ГГГГ</b>:",
        )
        return

    data = await state.update_data(commissioned_at=parsed.isoformat())
    await state.set_state(AddBikeForm.confirm)

    await message.answer(
        "📋 <b>Проверьте данные:</b>\n\n"
        f"🔢 Номер: <b>{data['bike_number']}</b>\n"
        f"🏍 Модель: <b>{data['model']}</b>\n"
        f"🏪 Склад: <b>{data['store_name']}</b>\n"
        f"📅 Дата: <b>{raw}</b>\n"
        f"📊 Статус: {STATUS_EMOJI['online']} {STATUS_LABEL['online']}\n\n"
        "Всё верно?",
        reply_markup=add_bike_confirm_kb(),
    )


# ── Step 5: Confirm ────────────────────────────────────────────────────


@router.callback_query(AddBikeForm.confirm, AddBikeConfirmCB.filter(F.action == "save"))
async def confirm_add_bike(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Create the bike record in the database."""
    await callback.answer()

    data = await state.get_data()
    commissioned = datetime.strptime(data["commissioned_at"], "%Y-%m-%d").date()

    bike = Bike(
        bike_number=data["bike_number"],
        model=data["model"],
        store_id=data["store_id"],
        commissioned_at=commissioned,
    )
    market_session.add(bike)
    await market_session.flush()

    logger.info(
        "Bike added: {number} ({model}) at store {store}",
        number=data["bike_number"],
        model=data["model"],
        store=data["store_name"],
    )

    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ Байк <b>{data['bike_number']}</b> успешно добавлен!\n\n"
        f"🏍 {data['model']}\n"
        f"🏪 {data['store_name']}\n"
        f"📊 {STATUS_EMOJI['online']} На линии",
        reply_markup=bike_menu_kb(),
    )


@router.callback_query(AddBikeForm.confirm, AddBikeConfirmCB.filter(F.action == "cancel"))
async def cancel_add_bike(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel adding a bike."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "❌ Добавление байка отменено.",
        reply_markup=bike_menu_kb(),
    )
