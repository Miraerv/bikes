"""Stage 3 — Usage log handlers (BIKE-30, BIKE-31, BIKE-33)."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from aiogram import F, Router
from loguru import logger
from sqlalchemy import select

from app.bot.keyboards.builders import (
    main_menu_kb,
    store_select_kb,
    usage_active_logs_kb,
    usage_active_store_select_kb,
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
from app.core.admin_user_lookup import search_admin_users_by_name
from app.core.store_access import get_accessible_stores, guard_store_access
from app.core.tz import now_display, to_yakutsk
from app.core.usage_flow import (
    TakeBikeDraft,
    build_take_bike_confirmation,
    create_usage_log,
    finish_usage_log,
    format_active_shift_lines,
    get_active_usage_log,
    list_active_usage_logs,
    usage_shift_summary,
)
from app.db.models.bike import Bike, BikeStatus

if TYPE_CHECKING:
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.bot_user import BotUser

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
    bot_user: BotUser | None = None,
) -> None:
    """Step 1: Choose store."""
    await callback.answer()

    stores = await get_accessible_stores(market_session, bot_user)

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
    bot_user: BotUser | None = None,
) -> None:
    """Step 2: Choose bike (only online bikes at the store)."""
    if not await guard_store_access(callback, bot_user, callback_data.store_id):
        return
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
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Step 3: Prompt supervisor to type courier name for search."""
    if not await guard_store_access(callback, bot_user, callback_data.store_id):
        return
    await callback.answer()

    bike = await market_session.get(Bike, callback_data.bike_id)
    if bike is None or bike.store_id != callback_data.store_id:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Байк не найден на выбранном складе.",
            reply_markup=usage_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(
        bike_id=callback_data.bike_id,
        store_id=callback_data.store_id,
    )
    await state.set_state(TakeBikeForm.courier_search)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔍 <b>Поиск курьера</b>\n\nВведите имя или фамилию курьера:",
    )


@router.message(TakeBikeForm.courier_search, F.text)
async def take_courier_search(
    message: Message,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Step 3b: Search couriers by name/surname and show results."""
    if message.text is None:
        await message.answer("Введите имя или фамилию курьера:")
        return

    query_text = message.text.strip()
    data = await state.get_data()

    couriers = await search_admin_users_by_name(market_session, query_text, limit=20)

    if not couriers:
        await message.answer(
            f"⚠️ По запросу «<b>{query_text}</b>» никого не найдено.\n\n"
            "Попробуйте ещё раз — введите имя или фамилию:",
        )
        return

    await state.set_state(TakeBikeForm.courier)
    await message.answer(
        f"👤 Найдено: <b>{len(couriers)}</b>\n\nВыберите курьера:",
        reply_markup=usage_courier_select_kb(
            couriers,
            data["bike_id"],
            data["store_id"],
        ),
    )


@router.callback_query(TakeBikeForm.courier, UsageCourierSelectCB.filter())
async def take_confirm(
    callback: CallbackQuery,
    callback_data: UsageCourierSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Step 4: Show confirmation."""
    if not await guard_store_access(callback, bot_user, callback_data.store_id):
        return
    await callback.answer()

    draft = TakeBikeDraft(
        bike_id=callback_data.bike_id,
        courier_id=callback_data.courier_id,
        store_id=callback_data.store_id,
    )
    confirmation = await build_take_bike_confirmation(market_session, draft, bot_user)

    await state.update_data(
        bike_id=draft.bike_id,
        courier_id=draft.courier_id,
        store_id=draft.store_id,
        bike_label=confirmation.bike_label,
        courier_label=confirmation.courier_label,
        store_label=confirmation.store_label,
    )
    await state.set_state(TakeBikeForm.confirm)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "📋 <b>Подтвердите взятие байка:</b>\n\n"
        f"🚲 Байк: <b>{confirmation.bike_label}</b>\n"
        f"👤 Курьер: <b>{confirmation.courier_label}</b>\n"
        f"🏪 Склад: <b>{confirmation.store_label}</b>\n\n"
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

    draft = TakeBikeDraft(
        bike_id=cast("int", data["bike_id"]),
        courier_id=cast("int", data["courier_id"]),
        store_id=cast("int", data["store_id"]),
    )
    log = create_usage_log(draft)
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
    bot_user: BotUser | None = None,
) -> None:
    """Show stores that have active shifts."""
    await callback.answer()

    stores = await get_accessible_stores(market_session, bot_user)

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
    bot_user: BotUser | None = None,
) -> None:
    """Show active shifts at the selected store."""
    if callback_data.store_id > 0 and not await guard_store_access(
        callback,
        bot_user,
        callback_data.store_id,
    ):
        return
    await callback.answer()

    logs = await list_active_usage_logs(
        market_session,
        store_id=callback_data.store_id,
        bot_user=bot_user,
    )

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
    bot_user: BotUser | None = None,
) -> None:
    """Ask for confirmation before ending the shift."""
    await callback.answer()

    log = await get_active_usage_log(
        market_session,
        log_id=callback_data.log_id,
        bot_user=bot_user,
    )
    if log is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Смена не найдена или уже завершена.",
            reply_markup=usage_menu_kb(),
        )
        return

    summary = usage_shift_summary(log)
    started = to_yakutsk(summary.started_at).strftime("%d.%m %H:%M")

    await callback.message.edit_text(  # type: ignore[union-attr]
        "⚠️ <b>Завершить смену?</b>\n\n"
        f"🚲 {summary.bike_label}\n"
        f"👤 {summary.courier_name}\n"
        f"🏪 {summary.store_name}\n"
        f"🕐 Начало: {started}",
        reply_markup=usage_return_confirm_kb(summary.log_id),
    )


@router.callback_query(UsageReturnConfirmCB.filter(F.confirm == True))  # noqa: E712
async def return_save(
    callback: CallbackQuery,
    callback_data: UsageReturnConfirmCB,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """End the shift — set ended_at = now."""
    await callback.answer()

    summary = await finish_usage_log(
        market_session,
        log_id=callback_data.log_id,
        bot_user=bot_user,
    )
    if summary is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Смена не найдена или уже завершена.",
            reply_markup=usage_menu_kb(),
        )
        return

    logger.info(
        "Usage log ended: log_id={log_id}, bike={bike}, courier={courier}",
        log_id=summary.log_id,
        bike=summary.bike_number,
        courier=summary.courier_name,
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ Смена завершена!\n\n"
        f"🚲 {summary.bike_number}\n"
        f"👤 {summary.courier_name}\n"
        f"🕐 {to_yakutsk(summary.started_at).strftime('%H:%M')}"
        f" → {to_yakutsk(summary.ended_at).strftime('%H:%M')}",
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
    bot_user: BotUser | None = None,
) -> None:
    """Choose store to see active shifts."""
    await callback.answer()

    stores = await get_accessible_stores(market_session, bot_user)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "👀 <b>Кто на байке</b>\n\nВыберите склад:",
        reply_markup=usage_active_store_select_kb(stores),
    )


@router.callback_query(UsageActiveStoreCB.filter())
async def active_show_shifts(
    callback: CallbackQuery,
    callback_data: UsageActiveStoreCB,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Show all active shifts at the selected store."""
    if callback_data.store_id > 0 and not await guard_store_access(
        callback,
        bot_user,
        callback_data.store_id,
    ):
        return
    await callback.answer()

    logs = await list_active_usage_logs(
        market_session,
        store_id=callback_data.store_id,
        bot_user=bot_user,
    )

    if not logs:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 Нет активных смен.",
            reply_markup=usage_menu_kb(),
        )
        return

    summaries = [usage_shift_summary(log) for log in logs]
    lines = format_active_shift_lines(summaries)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "\n".join(lines),
        reply_markup=usage_menu_kb(),
    )
