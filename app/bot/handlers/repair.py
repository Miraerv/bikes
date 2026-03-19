"""Stage 5 — Repair handlers (BIKE-50..BIKE-53)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.keyboards.builders import (
    BREAKDOWN_TYPE_EMOJI,
    BREAKDOWN_TYPE_LABEL,
    main_menu_kb,
    repair_active_list_kb,
    repair_bike_select_kb,
    repair_breakdown_select_kb,
    repair_complete_confirm_kb,
    repair_menu_kb,
    repair_my_list_kb,
    repair_pickup_confirm_kb,
    store_select_kb,
)
from app.bot.keyboards.callbacks import (
    RepairBikeSelectCB,
    RepairBreakdownSelectCB,
    RepairBreakdownSkipCB,
    RepairCompleteConfirmCB,
    RepairMechanicSelectCB,
    RepairMenuCB,
    RepairPickupConfirmCB,
    RepairSelectCB,
    StoreSelectCB,
)
from app.bot.states.bike import RepairCompleteForm, RepairPickupForm
from app.core.config import settings
from app.core.tz import to_yakutsk
from app.db.models.bike import Bike, BikeStatus
from app.db.models.bike_breakdown import BikeBreakdown
from app.db.models.bike_repair import BikeRepair
from app.db.models.bot_user import BotUser, UserRole
from app.db.models.store import Store

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from sqlalchemy.ext.asyncio import AsyncSession

router = Router(name="repair")


# ── Helpers ────────────────────────────────────────────────────────────


def _mechanic_select_kb(mechanics: list[BotUser]) -> InlineKeyboardMarkup:
    """Build inline keyboard for selecting a mechanic (from BotUser)."""
    buttons = []
    for mech in mechanics:
        buttons.append([InlineKeyboardButton(
            text=f"🔧 {mech.name}",
            callback_data=RepairMechanicSelectCB(mechanic_id=mech.id).pack(),
        )])
    buttons.append([InlineKeyboardButton(
        text="❌ Отмена",
        callback_data=RepairPickupConfirmCB(action="cancel").pack(),
    )])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ── Repair sub-menu ─────────────────────────────────────────────────────


@router.callback_query(RepairMenuCB.filter(F.action == "open"))
async def open_repair_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show repair sub-menu."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🛠 <b>Ремонт</b>\n\nВыберите действие:",
        reply_markup=repair_menu_kb(),
    )


@router.callback_query(RepairMenuCB.filter(F.action == "back"))
async def back_to_main(callback: CallbackQuery) -> None:
    """Return to main menu."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  BIKE-50 — Repair Pickup
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(RepairMenuCB.filter(F.action == "pickup"))
async def rp_choose_store(
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
            reply_markup=repair_menu_kb(),
        )
        return

    await state.set_state(RepairPickupForm.store)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "📥 <b>Забрать байк на ремонт</b>\n\nВыберите склад:",
        reply_markup=store_select_kb(stores, purpose="rp_pickup"),
    )


@router.callback_query(
    RepairPickupForm.store,
    StoreSelectCB.filter(F.purpose == "rp_pickup"),
)
async def rp_choose_bike(
    callback: CallbackQuery,
    callback_data: StoreSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Step 2: Choose bike (inspection / repair status only)."""
    await callback.answer()
    store_id = callback_data.store_id

    result = await market_session.execute(
        select(Bike)
        .where(
            Bike.store_id == store_id,
            Bike.status.in_([BikeStatus.INSPECTION, BikeStatus.REPAIR]),
        )
        .order_by(Bike.bike_number),
    )
    bikes = list(result.scalars().all())

    if not bikes:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 На этом складе нет байков для ремонта\n"
            "(нужен статус 🟡 Проверка или 🔴 Ремонт).",
            reply_markup=repair_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(store_id=store_id)
    await state.set_state(RepairPickupForm.bike)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚲 Выберите <b>байк</b> для ремонта:",
        reply_markup=repair_bike_select_kb(bikes, store_id),
    )


# ── BIKE-53 — Breakdown linking ─────────────────────────────────────────


@router.callback_query(RepairPickupForm.bike, RepairBikeSelectCB.filter())
async def rp_choose_breakdown(
    callback: CallbackQuery,
    callback_data: RepairBikeSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Step 3: Link to an existing breakdown (optional)."""
    await callback.answer()
    bike_id = callback_data.bike_id
    await state.update_data(bike_id=bike_id)

    # Find open breakdowns for this bike
    result = await market_session.execute(
        select(BikeBreakdown)
        .where(BikeBreakdown.bike_id == bike_id)
        .order_by(BikeBreakdown.reported_at.desc())
        .limit(10),
    )
    breakdowns = list(result.scalars().all())

    if not breakdowns:
        # No breakdowns — skip directly to mechanic select / auto-assign
        await state.update_data(breakdown_id=None)
        await _pick_mechanic(callback, state, market_session, bot_user)
        return

    await state.set_state(RepairPickupForm.breakdown)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔗 Привязать к <b>поломке</b>?\n\n"
        "Выберите поломку или пропустите:",
        reply_markup=repair_breakdown_select_kb(breakdowns),
    )


@router.callback_query(RepairPickupForm.breakdown, RepairBreakdownSelectCB.filter())
async def rp_breakdown_selected(
    callback: CallbackQuery,
    callback_data: RepairBreakdownSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Breakdown selected — move to mechanic selection."""
    await callback.answer()
    await state.update_data(breakdown_id=callback_data.breakdown_id)
    await _pick_mechanic(callback, state, market_session, bot_user)


@router.callback_query(
    RepairPickupForm.breakdown,
    RepairBreakdownSkipCB.filter(F.action == "skip"),
)
async def rp_breakdown_skip(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Skip breakdown linking — move to mechanic selection."""
    await callback.answer()
    await state.update_data(breakdown_id=None)
    await _pick_mechanic(callback, state, market_session, bot_user)


async def _pick_mechanic(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Auto-assign if caller is a mechanic, otherwise show selection."""
    if bot_user and bot_user.is_mechanic:
        # Auto-assign current mechanic
        await state.update_data(
            mechanic_id=bot_user.id,
            mechanic_name=bot_user.name,
        )
        await _show_pickup_confirm(callback, state, market_session)
        return

    # Supervisor / admin — show mechanic list
    result = await market_session.execute(
        select(BotUser)
        .where(BotUser.role == UserRole.MECHANIC)
        .order_by(BotUser.name),
    )
    mechanics = list(result.scalars().all())

    if not mechanics:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Нет активных мастеров.\n"
            "Добавьте мастера через регистрацию в боте.",
            reply_markup=repair_menu_kb(),
        )
        await state.clear()
        return

    await state.set_state(RepairPickupForm.mechanic)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔧 Выберите <b>мастера</b>:",
        reply_markup=_mechanic_select_kb(mechanics),
    )


# ── Mechanic selection ──────────────────────────────────────────────────


@router.callback_query(RepairPickupForm.mechanic, RepairMechanicSelectCB.filter())
async def rp_mechanic_selected(
    callback: CallbackQuery,
    callback_data: RepairMechanicSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Mechanic selected — show pickup confirmation."""
    await callback.answer()

    mechanic = await market_session.get(BotUser, callback_data.mechanic_id)
    if not mechanic:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Мастер не найден.",
            reply_markup=repair_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(
        mechanic_id=mechanic.id,
        mechanic_name=mechanic.name,
    )
    await _show_pickup_confirm(callback, state, market_session)


async def _show_pickup_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Build and show the repair pickup confirmation screen."""
    data = await state.get_data()

    bike = await market_session.get(Bike, data["bike_id"])
    store_result = await market_session.execute(
        select(Store).where(Store.id == data["store_id"]),
    )
    store = store_result.scalar_one_or_none()

    bike_label = f"{bike.bike_number} — {bike.model}" if bike else "—"
    store_label = store.display_name if store else "—"
    mechanic_name = data.get("mechanic_name", "—")

    # Breakdown info
    breakdown_label = "— (без привязки)"
    breakdown_id = data.get("breakdown_id")
    if breakdown_id:
        bd = await market_session.get(BikeBreakdown, breakdown_id)
        if bd:
            bd_emoji = BREAKDOWN_TYPE_EMOJI.get(bd.breakdown_type.value, "❓")
            bd_type_label = BREAKDOWN_TYPE_LABEL.get(
                bd.breakdown_type.value, bd.breakdown_type.value,
            )
            reported = to_yakutsk(bd.reported_at).strftime("%d.%m.%Y")
            breakdown_label = f"{bd_emoji} {bd_type_label} ({reported})"

    await state.update_data(bike_label=bike_label, store_label=store_label)
    await state.set_state(RepairPickupForm.confirm)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "📋 <b>Подтвердите забор байка:</b>\n\n"
        f"🚲 Байк: <b>{bike_label}</b>\n"
        f"🏪 Склад: <b>{store_label}</b>\n"
        f"🔗 Поломка: <b>{breakdown_label}</b>\n"
        f"🔧 Мастер: <b>{mechanic_name}</b>\n\n"
        "Всё верно?",
        reply_markup=repair_pickup_confirm_kb(),
    )


# ── Pickup confirmation ────────────────────────────────────────────────


@router.callback_query(
    RepairPickupForm.confirm,
    RepairPickupConfirmCB.filter(F.action == "save"),
)
async def rp_pickup_save(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Save the repair pickup record."""
    await callback.answer()
    data = await state.get_data()

    now = datetime.now()

    repair = BikeRepair(
        bike_id=data["bike_id"],
        breakdown_id=data.get("breakdown_id"),
        mechanic_id=data.get("mechanic_id"),
        mechanic_name=data.get("mechanic_name"),
        store_id=data["store_id"],
        picked_up_at=now,
    )
    market_session.add(repair)

    # Change bike status -> repair
    bike = await market_session.get(Bike, data["bike_id"])
    if bike and bike.status != BikeStatus.REPAIR:
        bike.status = BikeStatus.REPAIR
        logger.info(
            "Bike status changed to repair: bike_id={bike_id}",
            bike_id=bike.id,
        )

    logger.info(
        "Repair pickup: bike={bike}, mechanic={mechanic}, breakdown_id={bd_id}",
        bike=data.get("bike_label"),
        mechanic=data.get("mechanic_name"),
        bd_id=data.get("breakdown_id"),
    )

    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ Байк забран на ремонт!\n\n"
        f"🚲 {data.get('bike_label', '—')}\n"
        f"🔧 Мастер: {data.get('mechanic_name', '—')}",
        reply_markup=repair_menu_kb(),
    )


@router.callback_query(
    RepairPickupForm.confirm,
    RepairPickupConfirmCB.filter(F.action == "cancel"),
)
async def rp_pickup_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel repair pickup."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "❌ Забор байка отменён.",
        reply_markup=repair_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  BIKE-51 — Repair Complete
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(RepairMenuCB.filter(F.action == "complete"))
async def rp_complete_start(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Show list of active (in-progress) repairs."""
    await callback.answer()

    result = await market_session.execute(
        select(BikeRepair)
        .options(selectinload(BikeRepair.bike))
        .where(BikeRepair.completed_at.is_(None))
        .order_by(BikeRepair.picked_up_at.desc()),
    )
    repairs = list(result.scalars().all())

    if not repairs:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 Нет активных ремонтов.",
            reply_markup=repair_menu_kb(),
        )
        return

    await state.set_state(RepairCompleteForm.repair)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ <b>Завершить ремонт</b>\n\nВыберите ремонт:",
        reply_markup=repair_active_list_kb(repairs),
    )


@router.callback_query(RepairCompleteForm.repair, RepairSelectCB.filter())
async def rp_complete_select(
    callback: CallbackQuery,
    callback_data: RepairSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Select a repair — enter work description."""
    await callback.answer()
    repair_id = callback_data.repair_id

    repair = await market_session.get(BikeRepair, repair_id)
    if not repair:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Ремонт не найден.",
            reply_markup=repair_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(repair_id=repair_id)
    await state.set_state(RepairCompleteForm.work_description)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "📝 Введите <b>описание выполненных работ</b>:\n\n"
        "<i>Отправьте текстовое сообщение или «-» чтобы пропустить.</i>",
    )


@router.message(RepairCompleteForm.work_description, F.text)
async def rp_complete_description(
    message: Message,
    state: FSMContext,
) -> None:
    """Receive work description, move to duration."""
    desc = message.text.strip() if message.text else None
    if desc == "-":
        desc = None
    await state.update_data(work_description=desc)
    await state.set_state(RepairCompleteForm.duration)
    await message.answer(
        "⏱ Введите <b>время ремонта</b> (в минутах):\n\n"
        "<i>Отправьте число или «-» чтобы пропустить.</i>",
    )


@router.message(RepairCompleteForm.duration, F.text)
async def rp_complete_duration(
    message: Message,
    state: FSMContext,
) -> None:
    """Receive repair duration, move to cost."""
    text = message.text.strip() if message.text else ""
    duration = None
    if text != "-":
        try:
            duration = int(text)
            if duration <= 0:
                await message.answer("⚠️ Введите положительное число минут.")
                return
        except ValueError:
            await message.answer(
                "⚠️ Некорректный ввод. Введите число минут или «-» чтобы пропустить.",
            )
            return

    await state.update_data(repair_duration_minutes=duration)
    await state.set_state(RepairCompleteForm.cost)
    await message.answer(
        "💰 Введите <b>стоимость ремонта</b> (число):\n\n"
        "<i>Отправьте сумму или «-» чтобы пропустить.</i>",
    )


@router.message(RepairCompleteForm.cost, F.text)
async def rp_complete_cost(
    message: Message,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Receive cost, show confirmation."""
    text = message.text.strip() if message.text else ""
    cost = None
    if text != "-":
        try:
            cost = Decimal(text.replace(",", "."))
            if cost < 0:
                await message.answer("⚠️ Стоимость не может быть отрицательной.")
                return
        except InvalidOperation:
            await message.answer(
                "⚠️ Некорректный ввод. Введите число или «-» чтобы пропустить.",
            )
            return

    await state.update_data(cost=str(cost) if cost is not None else None)
    await _show_complete_confirm(message, state, market_session)


async def _show_complete_confirm(
    event: Message | CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Build and show the repair completion confirmation screen."""
    data = await state.get_data()

    repair = await market_session.get(BikeRepair, data["repair_id"])
    bike = repair.bike if repair else None

    bike_label = f"{bike.bike_number} — {bike.model}" if bike else "—"
    mechanic_name = repair.mechanic_name if repair else "—"
    work_desc = data.get("work_description") or "—"
    duration = data.get("repair_duration_minutes")
    duration_label = f"{duration} мин." if duration else "—"
    cost = data.get("cost")
    cost_label = f"{cost} ₽" if cost else "—"

    await state.update_data(bike_label=bike_label, mechanic_name=mechanic_name)
    await state.set_state(RepairCompleteForm.confirm)

    text = (
        "📋 <b>Подтвердите завершение ремонта:</b>\n\n"
        f"🚲 Байк: <b>{bike_label}</b>\n"
        f"🔧 Мастер: <b>{mechanic_name}</b>\n"
        f"📝 Работы: {work_desc}\n"
        f"⏱ Время: <b>{duration_label}</b>\n"
        f"💰 Стоимость: <b>{cost_label}</b>\n\n"
        "Всё верно?"
    )

    # event can be Message (from text input) or CallbackQuery
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(  # type: ignore[union-attr]
            text, reply_markup=repair_complete_confirm_kb(),
        )
    else:
        await event.answer(text, reply_markup=repair_complete_confirm_kb())


# ── Complete confirmation ──────────────────────────────────────────────


@router.callback_query(
    RepairCompleteForm.confirm,
    RepairCompleteConfirmCB.filter(F.action == "save"),
)
async def rp_complete_save(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Save the repair completion."""
    await callback.answer()
    data = await state.get_data()

    now = datetime.now()

    repair = await market_session.get(BikeRepair, data["repair_id"])
    if not repair:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Ремонт не найден.",
            reply_markup=repair_menu_kb(),
        )
        await state.clear()
        return

    repair.completed_at = now
    repair.work_description = data.get("work_description")
    repair.repair_duration_minutes = data.get("repair_duration_minutes")
    cost_str = data.get("cost")
    repair.cost = Decimal(cost_str) if cost_str else None

    # Change bike status -> online
    bike = await market_session.get(Bike, repair.bike_id)
    if bike and bike.status == BikeStatus.REPAIR:
        bike.status = BikeStatus.ONLINE
        logger.info(
            "Bike status changed to online: bike_id={bike_id}",
            bike_id=bike.id,
        )

    logger.info(
        "Repair completed: repair_id={rp_id}, bike={bike}, mechanic={mechanic}",
        rp_id=repair.id,
        bike=data.get("bike_label"),
        mechanic=data.get("mechanic_name"),
    )

    await state.clear()

    duration = data.get("repair_duration_minutes")
    duration_label = f"{duration} мин." if duration else "—"
    cost_label = f"{cost_str} ₽" if cost_str else "—"

    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ Ремонт завершён!\n\n"
        f"🚲 {data.get('bike_label', '—')}\n"
        f"🔧 Мастер: {data.get('mechanic_name', '—')}\n"
        f"⏱ Время: {duration_label}\n"
        f"💰 Стоимость: {cost_label}",
        reply_markup=repair_menu_kb(),
    )


@router.callback_query(
    RepairCompleteForm.confirm,
    RepairCompleteConfirmCB.filter(F.action == "cancel"),
)
async def rp_complete_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel repair completion."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "❌ Завершение ремонта отменено.",
        reply_markup=repair_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  BIKE-52 — My Repairs
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(RepairMenuCB.filter(F.action == "my_repairs"))
async def rp_my_repairs(
    callback: CallbackQuery,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Show repairs for the current Telegram user (auto-detected via bot_user)."""
    await callback.answer()

    if not bot_user:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ <b>Пользователь не найден</b>\n\n"
            "Ваш аккаунт не зарегистрирован.",
            reply_markup=repair_menu_kb(),
        )
        return

    # Find repairs by mechanic_id = bot_user.id (from bike_bot_roles)
    repairs_result = await market_session.execute(
        select(BikeRepair)
        .options(
            selectinload(BikeRepair.bike),
            selectinload(BikeRepair.store),
        )
        .where(BikeRepair.mechanic_id == bot_user.id)
        .order_by(BikeRepair.picked_up_at.desc())
        .limit(15),
    )
    repairs = list(repairs_result.scalars().all())

    if not repairs:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"📋 Ремонтов для <b>{bot_user.name}</b> не найдено.",
            reply_markup=repair_menu_kb(),
        )
        return

    lines = [f"📋 <b>Ремонты — {bot_user.name}</b>", ""]
    for rp in repairs:
        bike_num = rp.bike.bike_number if rp.bike else "—"
        bike_model = rp.bike.model if rp.bike else ""
        picked = to_yakutsk(rp.picked_up_at).strftime("%d.%m.%Y %H:%M")

        status_icon = "🔴" if rp.completed_at is None else "🟢"
        completed = (
            to_yakutsk(rp.completed_at).strftime("%d.%m.%Y %H:%M")
            if rp.completed_at
            else "в работе"
        )

        cost_str = f"{rp.cost} ₽" if rp.cost else "—"

        lines.append(
            f"{status_icon} <b>{bike_num}</b> {bike_model}\n"
            f"   📅 Забрал: {picked}\n"
            f"   📅 Готов: {completed}\n"
            f"   💰 {cost_str}"
            + (f"\n   📝 {rp.work_description}" if rp.work_description else "")
            + "\n",
        )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=repair_my_list_kb(repairs),
    )
