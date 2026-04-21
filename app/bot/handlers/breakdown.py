"""Stage 4 — Breakdown handlers (BIKE-40..BIKE-44)."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, cast

from aiogram import F, Router
from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.bot.keyboards.builders import (
    BREAKDOWN_TYPE_EMOJI,
    BREAKDOWN_TYPE_LABEL,
    breakdown_bike_select_kb,
    breakdown_confirm_kb,
    breakdown_courier_select_kb,
    breakdown_detail_kb,
    breakdown_history_kb,
    breakdown_menu_kb,
    breakdown_photo_kb,
    breakdown_type_kb,
    main_menu_kb,
    store_select_kb,
)
from app.bot.keyboards.callbacks import (
    BreakdownBikeSelectCB,
    BreakdownConfirmCB,
    BreakdownCourierSelectCB,
    BreakdownDetailCB,
    BreakdownHistoryCB,
    BreakdownMenuCB,
    BreakdownSkipPhotoCB,
    BreakdownTypeCB,
    StoreSelectCB,
)
from app.bot.states.bike import BreakdownForm
from app.core.admin_user_lookup import search_admin_users_by_name
from app.core.breakdown_flow import (
    BreakdownDraft,
    build_breakdown_confirmation,
    detect_last_usage_courier,
    save_breakdown,
)
from app.core.store_access import get_accessible_stores, guard_store_access
from app.core.tz import to_yakutsk
from app.db.models.admin_user import AdminUser
from app.db.models.bike import Bike, BikeStatus
from app.db.models.bike_breakdown import BikeBreakdown

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.bot_user import BotUser

router = Router(name="breakdown")




# ── Breakdown sub-menu ──────────────────────────────────────────────────


@router.callback_query(BreakdownMenuCB.filter(F.action == "open"))
async def open_breakdown_menu(callback: CallbackQuery, state: FSMContext) -> None:
    """Show breakdown sub-menu."""
    await state.clear()
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔧 <b>Поломки</b>\n\nВыберите действие:",
        reply_markup=breakdown_menu_kb(),
    )


@router.callback_query(BreakdownMenuCB.filter(F.action == "back"))
async def back_to_main(callback: CallbackQuery) -> None:
    """Return to main menu."""
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🏠 <b>Главное меню</b>\n\nВыберите раздел:",
        reply_markup=main_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  BIKE-40 — Создать поломку (Create breakdown)
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(BreakdownMenuCB.filter(F.action == "create"))
async def bd_choose_store(
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
            reply_markup=breakdown_menu_kb(),
        )
        return

    await state.set_state(BreakdownForm.store)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🔧 <b>Создать поломку</b>\n\nВыберите склад:",
        reply_markup=store_select_kb(stores, purpose="bd_create"),
    )


@router.callback_query(
    BreakdownForm.store,
    StoreSelectCB.filter(F.purpose == "bd_create"),
)
async def bd_choose_bike(
    callback: CallbackQuery,
    callback_data: StoreSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Step 2: Choose bike (exclude decommissioned)."""
    if not await guard_store_access(callback, bot_user, callback_data.store_id):
        return
    await callback.answer()
    store_id = callback_data.store_id

    result = await market_session.execute(
        select(Bike)
        .where(Bike.store_id == store_id, Bike.status != BikeStatus.DECOMMISSIONED)
        .order_by(Bike.bike_number),
    )
    bikes = list(result.scalars().all())

    if not bikes:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "📭 На этом складе нет активных байков.",
            reply_markup=breakdown_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(store_id=store_id)
    await state.set_state(BreakdownForm.bike)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "🚲 Выберите <b>байк</b>:",
        reply_markup=breakdown_bike_select_kb(bikes, store_id),
    )


@router.callback_query(BreakdownForm.bike, BreakdownBikeSelectCB.filter())
async def bd_choose_type(
    callback: CallbackQuery,
    callback_data: BreakdownBikeSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Step 3: Choose breakdown type."""
    if not await guard_store_access(callback, bot_user, callback_data.store_id):
        return
    await callback.answer()

    bike = await market_session.get(Bike, callback_data.bike_id)
    if bike is None or bike.store_id != callback_data.store_id:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Байк не найден на выбранном складе.",
            reply_markup=breakdown_menu_kb(),
        )
        await state.clear()
        return

    await state.update_data(bike_id=callback_data.bike_id)
    await state.set_state(BreakdownForm.breakdown_type)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "⚠️ Выберите <b>тип поломки</b>:",
        reply_markup=breakdown_type_kb(),
    )


@router.callback_query(BreakdownForm.breakdown_type, BreakdownTypeCB.filter())
async def bd_enter_description(
    callback: CallbackQuery,
    callback_data: BreakdownTypeCB,
    state: FSMContext,
) -> None:
    """Step 4: Enter description (text input)."""
    await callback.answer()
    await state.update_data(breakdown_type=callback_data.bd_type)
    await state.set_state(BreakdownForm.description)
    await callback.message.edit_text(  # type: ignore[union-attr]
        "📝 Введите <b>описание поломки</b>:\n\n"
        "<i>Отправьте текстовое сообщение или отправьте «-» чтобы пропустить.</i>",
    )


@router.message(BreakdownForm.description, F.text)
async def bd_receive_description(
    message: Message,
    state: FSMContext,
) -> None:
    """Receive description text, move to photo step."""
    desc = message.text.strip() if message.text else None
    if desc == "-":
        desc = None
    await state.update_data(description=desc, photo_ids=[])
    await state.set_state(BreakdownForm.photos)
    sent = await message.answer(
        "📷 Отправьте <b>фото поломки</b> (можно несколько).\n\n"
        "Когда закончите — нажмите «✅ Готово».\n"
        "Или нажмите «⏭ Пропустить» если фото нет.",
        reply_markup=breakdown_photo_kb(),
    )
    await state.update_data(_bd_photo_msg_id=sent.message_id)


# ── BIKE-41 — Photo upload ─────────────────────────────────────────────


@router.message(BreakdownForm.photos, F.photo)
async def bd_receive_photo(
    message: Message,
    state: FSMContext,
) -> None:
    """Receive a photo during breakdown creation."""
    data = await state.get_data()
    photo_ids: list[str] = data.get("photo_ids", [])

    if not message.photo:
        await message.answer("⚠️ Не удалось получить фото. Попробуйте ещё раз.")
        return

    # Take the largest photo size
    photo = message.photo[-1]
    photo_ids.append(photo.file_id)
    await state.update_data(photo_ids=photo_ids)

    # Delete the previous bot message with stale buttons
    old_msg_id = data.get("_bd_photo_msg_id")
    if old_msg_id and message.bot is not None:
        with contextlib.suppress(Exception):
            await message.bot.delete_message(message.chat.id, old_msg_id)

    sent = await message.answer(
        f"📷 Фото добавлено ({len(photo_ids)} шт.)\n\n"
        "Отправьте ещё или нажмите «✅ Готово».",
        reply_markup=breakdown_photo_kb(),
    )
    await state.update_data(_bd_photo_msg_id=sent.message_id)


@router.callback_query(
    BreakdownForm.photos,
    BreakdownSkipPhotoCB.filter(F.action.in_({"skip", "done"})),
)
async def bd_photos_done(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Skip photos or finish uploading — try auto-detect courier, or ask."""
    await callback.answer()
    data = await state.get_data()

    # BIKE-42 — Auto-detect last courier from usage log
    last_courier = await detect_last_usage_courier(
        market_session,
        bike_id=cast("int", data["bike_id"]),
    )

    if last_courier:
        # Auto-detected → go straight to confirmation
        await state.update_data(
            courier_id=last_courier.courier_id,
            courier_name=last_courier.courier_name,
        )
        await _show_bd_confirm(callback, state, market_session)
    else:
        # No usage log — ask supervisor to type courier name
        await state.set_state(BreakdownForm.courier)
        await callback.message.edit_text(  # type: ignore[union-attr]
            "👤 <b>Курьер не определён автоматически</b>\n\n"
            "Введите имя или часть имени курьера для поиска:",
        )


@router.message(BreakdownForm.courier, F.text)
async def bd_search_courier(
    message: Message,
    state: FSMContext,  # noqa: ARG001
    market_session: AsyncSession,
) -> None:
    """Search couriers by name and show matching results."""
    query_text = message.text.strip() if message.text else ""
    if not query_text:
        await message.answer("⚠️ Введите имя курьера для поиска.")
        return

    couriers = await search_admin_users_by_name(market_session, query_text, limit=10)

    if not couriers:
        await message.answer(
            f"🔍 По запросу «<b>{query_text}</b>» ничего не найдено.\n\n"
            "Попробуйте другое имя:",
        )
        return

    await message.answer(
        f"🔍 Найдено: <b>{len(couriers)}</b>\n\n"
        "Выберите курьера:",
        reply_markup=breakdown_courier_select_kb(couriers),
    )


@router.callback_query(BreakdownForm.courier, BreakdownCourierSelectCB.filter())
async def bd_manual_courier_select(
    callback: CallbackQuery,
    callback_data: BreakdownCourierSelectCB,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Supervisor manually picked the courier — show confirmation."""
    await callback.answer()

    courier = await market_session.get(AdminUser, callback_data.courier_id)
    courier_name = courier.display_name if courier else "—"

    await state.update_data(
        courier_id=callback_data.courier_id,
        courier_name=courier_name,
    )
    await _show_bd_confirm(callback, state, market_session)


def _breakdown_draft_from_state(data: dict[str, object]) -> BreakdownDraft:
    return BreakdownDraft(
        bike_id=cast("int", data["bike_id"]),
        store_id=cast("int", data["store_id"]),
        breakdown_type=cast("str", data["breakdown_type"]),
        description=cast("str | None", data.get("description")),
        photo_ids=tuple(cast("list[str]", data.get("photo_ids", []))),
        courier_id=cast("int", data["courier_id"]),
        courier_name=cast("str", data.get("courier_name", "—")),
    )


async def _show_bd_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Build and show the breakdown confirmation screen."""
    data = await state.get_data()
    draft = _breakdown_draft_from_state(data)
    confirmation = await build_breakdown_confirmation(market_session, draft)

    bd_type = draft.breakdown_type
    bd_emoji = BREAKDOWN_TYPE_EMOJI.get(bd_type, "❓")
    bd_label = BREAKDOWN_TYPE_LABEL.get(bd_type, bd_type)

    await state.update_data(
        bike_label=confirmation.bike_label,
        store_label=confirmation.store_label,
    )
    await state.set_state(BreakdownForm.confirm)

    await callback.message.edit_text(  # type: ignore[union-attr]
        "📋 <b>Подтвердите поломку:</b>\n\n"
        f"🚲 Байк: <b>{confirmation.bike_label}</b>\n"
        f"🏪 Склад: <b>{confirmation.store_label}</b>\n"
        f"{bd_emoji} Тип: <b>{bd_label}</b>\n"
        f"📝 Описание: {confirmation.description_label}\n"
        f"📷 Фото: <b>{confirmation.photo_count} шт.</b>\n"
        f"👤 Курьер: <b>{draft.courier_name}</b>\n\n"
        "Всё верно?",
        reply_markup=breakdown_confirm_kb(),
    )


# ── Confirmation ────────────────────────────────────────────────────────


@router.callback_query(
    BreakdownForm.confirm,
    BreakdownConfirmCB.filter(F.action == "save"),
)
async def bd_save(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """Save the breakdown record."""
    await callback.answer()
    data = await state.get_data()
    draft = _breakdown_draft_from_state(data)
    created = await save_breakdown(market_session, draft)

    if created.bike_status_changed:
        logger.info(
            "Bike status changed to inspection: bike_id={bike_id}",
            bike_id=draft.bike_id,
        )

    logger.info(
        "Breakdown created: id={bd_id}, bike={bike}, type={bd_type}, courier={courier}",
        bd_id=created.breakdown_id,
        bike=data.get("bike_label"),
        bd_type=draft.breakdown_type,
        courier=draft.courier_name,
    )

    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "✅ Поломка зафиксирована!\n\n"
        f"🚲 {data['bike_label']}\n"
        f"⚠️ {BREAKDOWN_TYPE_LABEL.get(draft.breakdown_type, draft.breakdown_type)}\n"
        f"📷 Фото: {len(draft.photo_ids)} шт.\n"
        f"👤 Курьер: {draft.courier_name}",
        reply_markup=breakdown_menu_kb(),
    )


@router.callback_query(
    BreakdownForm.confirm,
    BreakdownConfirmCB.filter(F.action == "cancel"),
)
async def bd_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel breakdown creation."""
    await callback.answer()
    await state.clear()
    await callback.message.edit_text(  # type: ignore[union-attr]
        "❌ Создание поломки отменено.",
        reply_markup=breakdown_menu_kb(),
    )


# ══════════════════════════════════════════════════════════════════════════
#  BIKE-44 — История поломок байка (Breakdown history)
# ══════════════════════════════════════════════════════════════════════════


@router.callback_query(BreakdownHistoryCB.filter())
async def show_breakdown_history(
    callback: CallbackQuery,
    callback_data: BreakdownHistoryCB,
    market_session: AsyncSession,
) -> None:
    """Show breakdown history for a specific bike — compact list."""
    await callback.answer()

    bike = await market_session.get(Bike, callback_data.bike_id)
    if bike is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Байк не найден.",
            reply_markup=main_menu_kb(),
        )
        return

    result = await market_session.execute(
        select(BikeBreakdown)
        .options(
            selectinload(BikeBreakdown.courier),
            selectinload(BikeBreakdown.photos),
        )
        .where(BikeBreakdown.bike_id == callback_data.bike_id)
        .order_by(BikeBreakdown.reported_at.desc())
        .limit(10),
    )
    breakdowns = list(result.scalars().all())

    if not breakdowns:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"📋 <b>Поломки байка #{bike.bike_number}</b>\n\n"
            "Поломок не зафиксировано.",
            reply_markup=breakdown_history_kb(breakdowns, bike.id),
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"📋 <b>Поломки байка #{bike.bike_number}</b>\n"
        f"Всего: {len(breakdowns)}\n\n"
        "Нажмите на поломку для подробностей:",
        reply_markup=breakdown_history_kb(breakdowns, bike.id),
    )


# ── Breakdown detail ───────────────────────────────────────────────────


@router.callback_query(BreakdownDetailCB.filter())
async def breakdown_detail(
    callback: CallbackQuery,
    callback_data: BreakdownDetailCB,
    market_session: AsyncSession,
    bot: Bot,
) -> None:
    """Show full detail for a single breakdown + send photos."""
    await callback.answer()

    result = await market_session.execute(
        select(BikeBreakdown)
        .options(
            selectinload(BikeBreakdown.courier),
            selectinload(BikeBreakdown.reporter),
            selectinload(BikeBreakdown.photos),
            selectinload(BikeBreakdown.bike),
        )
        .where(BikeBreakdown.id == callback_data.breakdown_id),
    )
    bd = result.scalar_one_or_none()

    if bd is None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Поломка не найдена.",
            reply_markup=main_menu_kb(),
        )
        return

    bd_emoji = BREAKDOWN_TYPE_EMOJI.get(bd.breakdown_type.value, "❓")
    bd_label = BREAKDOWN_TYPE_LABEL.get(bd.breakdown_type.value, bd.breakdown_type.value)
    courier_name = bd.courier.display_name if bd.courier else "—"
    reporter_name = bd.reporter.display_name if bd.reporter else "—"
    reported = to_yakutsk(bd.reported_at).strftime("%d.%m.%Y %H:%M")
    bike_num = bd.bike.bike_number if bd.bike else "—"
    photo_count = len(bd.photos) if bd.photos else 0

    text = (
        f"{bd_emoji} <b>{bd_label}</b>\n\n"
        f"🚲 Байк: <b>#{bike_num}</b>\n"
        f"👤 Курьер: <b>{courier_name}</b>\n"
        f"📋 Зафиксировал: <b>{reporter_name}</b>\n"
        f"🕐 Дата: <b>{reported}</b>\n"
        f"📷 Фото: <b>{photo_count} шт.</b>\n"
    )
    if bd.description:
        text += f"\n📝 <b>Описание:</b>\n{bd.description}\n"

    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        reply_markup=breakdown_detail_kb(callback_data.bike_id),
    )

    # Send photos as separate messages
    chat_id = callback.message.chat.id  # type: ignore[union-attr]
    caption = f"{bd_emoji} {bd_label} — байк #{bike_num}"
    for photo in bd.photos or []:
        await bot.send_photo(chat_id, photo.photo_url, caption=caption)
