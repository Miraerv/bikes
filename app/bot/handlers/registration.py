"""Registration & admin approval handlers (Stage 9 — Roles)."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from aiogram import F, Router
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from loguru import logger
from sqlalchemy import select
from sqlalchemy.sql import func as sql_func

from app.bot.keyboards.callbacks import (
    AdminApprovalCB,
    AdminRoleSelectCB,
    AdminSupervisorStoreActionCB,
    AdminSupervisorStoreCB,
    RegistrationCB,
)
from app.bot.states.bike import RegistrationForm
from app.core.admin_access import get_admin_telegram_ids, is_admin_actor
from app.core.store_access import get_accessible_stores
from app.db.models.admin_user import AdminUser
from app.db.models.bot_user import ROLE_LABEL, BotUser, UserRole
from app.db.models.bot_user_admin_notification import BotUserAdminNotification

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.store import Store

router = Router(name="registration")


# ── Keyboards ──────────────────────────────────────────────────────────


def _apply_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📝 Отправить заявку",
            callback_data=RegistrationCB(action="apply").pack(),
        )],
    ])


def _share_contact_kb() -> ReplyKeyboardMarkup:
    """Reply keyboard with 'Share contact' button."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _approval_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=AdminApprovalCB(
                    user_id=user_id, action="approve",
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=AdminApprovalCB(
                    user_id=user_id, action="reject",
                ).pack(),
            ),
        ],
    ])


def _role_select_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👑 Админ",
            callback_data=AdminRoleSelectCB(
                user_id=user_id, role="admin",
            ).pack(),
        )],
        [InlineKeyboardButton(
            text="📋 Супервайзер",
            callback_data=AdminRoleSelectCB(
                user_id=user_id, role="supervisor",
            ).pack(),
        )],
        [InlineKeyboardButton(
            text="🔧 Мастер",
            callback_data=AdminRoleSelectCB(
                user_id=user_id, role="mechanic",
            ).pack(),
        )],
        [InlineKeyboardButton(
            text="🚚 Курьер",
            callback_data=AdminRoleSelectCB(
                user_id=user_id, role="courier",
            ).pack(),
        )],
    ])


def _supervisor_store_kb(
    user_id: int,
    selected_store_ids: set[int],
    stores: list[Store],
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for store in stores:
        is_selected = store.id in selected_store_ids
        prefix = "✅" if is_selected else "⬜️"
        rows.append([
            InlineKeyboardButton(
                text=f"{prefix} {store.display_name}",
                callback_data=AdminSupervisorStoreCB(
                    user_id=user_id,
                    store_id=store.id,
                ).pack(),
            ),
        ])

    rows.append([
        InlineKeyboardButton(
            text=f"💾 Сохранить ({len(selected_store_ids)})",
            callback_data=AdminSupervisorStoreActionCB(
                user_id=user_id,
                action="save",
            ).pack(),
        ),
    ])
    rows.append([
        InlineKeyboardButton(
            text="← Назад к ролям",
            callback_data=AdminSupervisorStoreActionCB(
                user_id=user_id,
                action="back",
            ).pack(),
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _normalize_phone(phone: str) -> str:
    """Strip everything except digits from a phone number."""
    return "".join(c for c in phone if c.isdigit())


def _phone_lookup_variants(phone_digits: str) -> set[str]:
    """Return phone variants used to match admin panel records."""
    variants = {phone_digits}
    if phone_digits.startswith("7") and len(phone_digits) == 11:
        variants.add("8" + phone_digits[1:])
        variants.add("+" + phone_digits)
    elif phone_digits.startswith("8") and len(phone_digits) == 11:
        variants.add("7" + phone_digits[1:])
        variants.add("+7" + phone_digits[1:])
    return variants


async def _notify_other_admins(
    bot: Bot,
    market_session: AsyncSession,
    user_id: int,
    actor_tg_id: int,
    text: str,
) -> None:
    """Edit the original admin notifications except for the acting admin."""
    result = await market_session.execute(
        select(BotUserAdminNotification).where(
            BotUserAdminNotification.bot_user_id == user_id,
        ),
    )
    notifications = result.scalars().all()
    for notification in notifications:
        if notification.admin_telegram_id == actor_tg_id:
            continue
        try:
            await bot.edit_message_text(
                chat_id=notification.admin_telegram_id,
                message_id=notification.message_id,
                text=text,
            )
        except Exception:
            logger.warning(
                "Could not update admin notification tg_id={tg_id} message_id={message_id}",
                tg_id=notification.admin_telegram_id,
                message_id=notification.message_id,
            )


# ── Registration flow ──────────────────────────────────────────────────


@router.callback_query(RegistrationCB.filter(F.action == "apply"))
async def reg_start(
    callback: CallbackQuery,
    state: FSMContext,
    market_session: AsyncSession,
) -> None:
    """User wants to apply — ask them to share their phone contact."""
    await callback.answer()

    tg_id = callback.from_user.id
    result = await market_session.execute(
        select(BotUser).where(BotUser.telegram_id == tg_id),
    )
    existing = result.scalar_one_or_none()

    if existing:
        if existing.is_pending:
            await callback.message.edit_text(  # type: ignore[union-attr]
                "⏳ Ваша заявка уже на рассмотрении.\n"
                "Ожидайте решения администратора.",
            )
        else:
            await callback.message.edit_text(  # type: ignore[union-attr]
                f"✅ Вы уже зарегистрированы: {existing.role_label}",
            )
        return

    await state.set_state(RegistrationForm.name)  # reusing the 'name' state for contact
    # Can't edit_text to reply keyboard, send new message
    await callback.message.answer(  # type: ignore[union-attr]
        "📱 <b>Поделитесь контактом</b>\n\n"
        "Нажмите кнопку ниже, чтобы отправить свой номер телефона.\n"
        "Мы найдём вас в системе автоматически.",
        reply_markup=_share_contact_kb(),
    )


@router.message(RegistrationForm.name, F.contact)
async def reg_contact(
    message: Message,
    state: FSMContext,
    market_session: AsyncSession,
    bot: Bot,
) -> None:
    """Receive shared contact — validate, lookup boom_admin_users, create BotUser."""
    contact = message.contact
    tg_id = message.from_user.id  # type: ignore[union-attr]

    if contact is None:
        await message.answer(
            "⚠️ Пожалуйста, нажмите кнопку <b>«📱 Поделиться номером»</b> ниже.",
            reply_markup=_share_contact_kb(),
        )
        return

    # 1. Verify it's the user's OWN contact
    if contact.user_id != tg_id:
        await message.answer(
            "⚠️ Пожалуйста, отправьте <b>свой</b> контакт, а не чужой.\n"
            "Нажмите кнопку «📱 Поделиться номером».",
            reply_markup=_share_contact_kb(),
        )
        return

    phone_raw = contact.phone_number or ""
    phone_digits = _normalize_phone(phone_raw)

    if not phone_digits:
        await message.answer(
            "⚠️ Не удалось получить номер телефона. Попробуйте ещё раз.",
            reply_markup=_share_contact_kb(),
        )
        return

    # 2. Search boom_admin_users by phone (try multiple formats)
    admin_user = None
    for variant in _phone_lookup_variants(phone_digits):
        result = await market_session.execute(
            select(AdminUser).where(
                sql_func.replace(
                    sql_func.replace(AdminUser.phone, "+", ""), " ", "",
                ) == variant,
            ).limit(1),
        )
        admin_user = result.scalar_one_or_none()
        if admin_user:
            break

    if not admin_user:
        await state.clear()
        await message.answer(
            "❌ <b>Номер не найден в системе</b>\n\n"
            f"Телефон: <code>{phone_raw}</code>\n\n"
            "Обратитесь к администратору — вас должны сначала "
            "добавить в панель управления.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # 3. Create BotUser with name from admin panel + admin_user_id
    surname = f" {admin_user.surname}" if admin_user.surname else ""
    name = f"{admin_user.name}{surname}"
    if not name.strip():
        name = "—"

    bot_user = BotUser(
        telegram_id=tg_id,
        admin_user_id=admin_user.id,
        name=name,
        role=UserRole.PENDING,
    )
    market_session.add(bot_user)
    await market_session.flush()

    await state.clear()

    logger.info(
        "New registration via contact: user={name} phone={phone} tg_id={tg_id}",
        name=name,
        phone=phone_raw,
        tg_id=tg_id,
    )

    await message.answer(
        "✅ <b>Заявка отправлена!</b>\n\n"
        f"👤 Имя: <b>{name}</b>\n"
        f"📱 Телефон: <code>{phone_raw}</code>\n\n"
        "Ожидайте одобрения администратора.",
        reply_markup=ReplyKeyboardRemove(),
    )

    # 4. Notify admin
    tg_username = message.from_user.username or ""  # type: ignore[union-attr]
    tg_link = f"@{tg_username}" if tg_username else f"<code>{phone_raw}</code>"
    admin_message = (
        "🆕 <b>Новая заявка на доступ</b>\n\n"
        f"👤 Имя: <b>{name}</b>\n"
        f"📱 Телефон: <code>{phone_raw}</code>\n"
        f"💬 Telegram: {tg_link}"
    )
    for tg_admin_id in await get_admin_telegram_ids(market_session):
        try:
            sent = await bot.send_message(
                tg_admin_id,
                admin_message,
                reply_markup=_approval_kb(bot_user.id),
            )
            market_session.add(BotUserAdminNotification(
                bot_user_id=bot_user.id,
                admin_telegram_id=tg_admin_id,
                message_id=sent.message_id,
            ))
        except Exception:
            logger.warning(
                "Could not notify admin tg_id={tg_id} about registration",
                tg_id=tg_admin_id,
            )


@router.message(RegistrationForm.name, F.text)
async def reg_text_instead_of_contact(
    message: Message,
) -> None:
    """User sent text instead of sharing contact."""
    await message.answer(
        "⚠️ Пожалуйста, нажмите кнопку <b>«📱 Поделиться номером»</b> ниже.\n"
        "Не вводите номер текстом.",
        reply_markup=_share_contact_kb(),
    )


# ── Admin approval flow ────────────────────────────────────────────────


@router.callback_query(AdminApprovalCB.filter(F.action == "approve"))
async def admin_approve(
    callback: CallbackQuery,
    callback_data: AdminApprovalCB,
    market_session: AsyncSession,
    bot_user: BotUser | None = None,
) -> None:
    """Admin approves — show role selection."""
    if not is_admin_actor(bot_user, callback.from_user.id):
        await callback.answer("⛔️ Только администратор может одобрять заявки.")
        return

    await callback.answer()
    user = await market_session.get(BotUser, callback_data.user_id)
    if not user:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Пользователь не найден.",
        )
        return

    if not user.is_pending:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"✅ <b>{user.name}</b> уже одобрен.\n\n"
            f"Роль: {user.role_label}",
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"👤 <b>{user.name}</b>\n\n"
        "Выберите роль:",
        reply_markup=_role_select_kb(user.id),
    )


@router.callback_query(AdminApprovalCB.filter(F.action == "reject"))
async def admin_reject(
    callback: CallbackQuery,
    callback_data: AdminApprovalCB,
    market_session: AsyncSession,
    bot: Bot,
    bot_user: BotUser | None = None,
) -> None:
    """Admin rejects the application."""
    if not is_admin_actor(bot_user, callback.from_user.id):
        await callback.answer("⛔️ Только администратор может отклонять заявки.")
        return

    await callback.answer()
    user = await market_session.get(BotUser, callback_data.user_id)
    if not user:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Пользователь не найден.",
        )
        return

    await market_session.delete(user)

    logger.info("Registration rejected: user={name}", name=user.name)

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"❌ Заявка <b>{user.name}</b> отклонена.",
    )

    await _notify_other_admins(
        bot,
        market_session,
        user.id,
        callback.from_user.id,
        f"❌ Заявка <b>{user.name}</b> отклонена.",
    )

    try:
        await bot.send_message(
            user.telegram_id,
            "❌ Ваша заявка на доступ была отклонена.\n"
            "Свяжитесь с администратором для уточнения.",
        )
    except Exception:
        logger.warning(
            "Could not notify rejected user tg_id={tg_id}", tg_id=user.telegram_id,
        )


@router.callback_query(AdminRoleSelectCB.filter())
async def admin_assign_role(
    callback: CallbackQuery,
    callback_data: AdminRoleSelectCB,
    market_session: AsyncSession,
    bot: Bot,
    state: FSMContext,
    bot_user: BotUser | None = None,
) -> None:
    """Admin assigns a specific role."""
    if not is_admin_actor(bot_user, callback.from_user.id):
        await callback.answer("⛔️ Только администратор.")
        return

    await callback.answer()
    user = await market_session.get(BotUser, callback_data.user_id)
    if not user:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Пользователь не найден.",
        )
        return

    if not user.is_pending:
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"✅ <b>{user.name}</b> уже одобрен.\n\n"
            f"Роль: {user.role_label}",
        )
        return

    if callback_data.role == UserRole.SUPERVISOR:
        stores = await get_accessible_stores(market_session)
        if not stores:
            await callback.message.edit_text(  # type: ignore[union-attr]
                "⚠️ Нет доступных складов для привязки супервайзера.",
            )
            return

        selected_store_ids = set(user.assigned_store_ids)
        await state.set_state(RegistrationForm.supervisor_stores)
        await state.update_data(
            supervisor_user_id=user.id,
            supervisor_store_ids=sorted(selected_store_ids),
        )
        await callback.message.edit_text(  # type: ignore[union-attr]
            f"👤 <b>{user.name}</b>\n\n"
            "Выберите склады, к которым будет привязан супервайзер:",
            reply_markup=_supervisor_store_kb(user.id, selected_store_ids, stores),
        )
        return

    user.role = callback_data.role
    user.store_ids = None
    role_label = ROLE_LABEL.get(callback_data.role, callback_data.role)

    logger.info(
        "Role assigned: user={name} role={role}",
        name=user.name,
        role=callback_data.role,
    )

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ <b>{user.name}</b> → {role_label}\n\n"
        "Роль успешно назначена.",
    )

    await _notify_other_admins(
        bot,
        market_session,
        user.id,
        callback.from_user.id,
        f"✅ <b>{user.name}</b> уже одобрен.\n\n"
        f"Роль: {role_label}",
    )

    try:
        await bot.send_message(
            user.telegram_id,
            f"🎉 <b>Вам выдан доступ!</b>\n\n"
            f"Роль: {role_label}\n\n"
            "Нажмите /start чтобы начать работу.",
        )
    except Exception:
        logger.warning(
            "Could not notify approved user tg_id={tg_id}", tg_id=user.telegram_id,
        )


@router.callback_query(
    RegistrationForm.supervisor_stores,
    AdminSupervisorStoreCB.filter(),
)
async def admin_toggle_supervisor_store(
    callback: CallbackQuery,
    callback_data: AdminSupervisorStoreCB,
    market_session: AsyncSession,
    state: FSMContext,
    bot_user: BotUser | None = None,
) -> None:
    """Toggle a store in supervisor assignment flow."""
    if not is_admin_actor(bot_user, callback.from_user.id):
        await callback.answer("⛔️ Только администратор.")
        return

    await callback.answer()
    data = await state.get_data()
    if data.get("supervisor_user_id") != callback_data.user_id:
        await state.update_data(
            supervisor_user_id=callback_data.user_id,
            supervisor_store_ids=[],
        )
        data = await state.get_data()

    store_ids = set(data.get("supervisor_store_ids", []))
    if callback_data.store_id in store_ids:
        store_ids.remove(callback_data.store_id)
    else:
        store_ids.add(callback_data.store_id)

    await state.update_data(supervisor_store_ids=sorted(store_ids))
    stores = await get_accessible_stores(market_session)
    await callback.message.edit_reply_markup(  # type: ignore[union-attr]
        reply_markup=_supervisor_store_kb(callback_data.user_id, store_ids, stores),
    )


@router.callback_query(
    RegistrationForm.supervisor_stores,
    AdminSupervisorStoreActionCB.filter(F.action == "back"),
)
async def admin_supervisor_store_back(
    callback: CallbackQuery,
    callback_data: AdminSupervisorStoreActionCB,
    market_session: AsyncSession,
    state: FSMContext,
    bot_user: BotUser | None = None,
) -> None:
    """Return from store selection to role selection."""
    if not is_admin_actor(bot_user, callback.from_user.id):
        await callback.answer("⛔️ Только администратор.")
        return

    await callback.answer()
    await state.clear()

    user = await market_session.get(BotUser, callback_data.user_id)
    if not user:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Пользователь не найден.",
        )
        return

    await callback.message.edit_text(  # type: ignore[union-attr]
        f"👤 <b>{user.name}</b>\n\n"
        "Выберите роль:",
        reply_markup=_role_select_kb(user.id),
    )


@router.callback_query(
    RegistrationForm.supervisor_stores,
    AdminSupervisorStoreActionCB.filter(F.action == "save"),
)
async def admin_save_supervisor_role(
    callback: CallbackQuery,
    callback_data: AdminSupervisorStoreActionCB,
    market_session: AsyncSession,
    bot: Bot,
    state: FSMContext,
    bot_user: BotUser | None = None,
) -> None:
    """Persist supervisor role and selected stores."""
    if not is_admin_actor(bot_user, callback.from_user.id):
        await callback.answer("⛔️ Только администратор.")
        return

    data = await state.get_data()
    store_ids = sorted(set(data.get("supervisor_store_ids", [])))
    if not store_ids:
        await callback.answer("Выберите хотя бы один склад.")
        return

    await callback.answer()
    user = await market_session.get(BotUser, callback_data.user_id)
    if not user:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Пользователь не найден.",
        )
        await state.clear()
        return

    stores = await get_accessible_stores(market_session)
    store_names = [
        store.display_name for store in stores if store.id in set(store_ids)
    ]

    user.role = UserRole.SUPERVISOR
    user.set_assigned_store_ids(store_ids)
    await state.clear()

    logger.info(
        "Supervisor assigned: user={name} stores={stores}",
        name=user.name,
        stores=json.dumps(store_ids, ensure_ascii=True),
    )

    store_lines = "\n".join(f"• {name}" for name in store_names)
    await callback.message.edit_text(  # type: ignore[union-attr]
        f"✅ <b>{user.name}</b> → {ROLE_LABEL[UserRole.SUPERVISOR]}\n\n"
        "Привязанные склады:\n"
        f"{store_lines}",
    )

    await _notify_other_admins(
        bot,
        market_session,
        user.id,
        callback.from_user.id,
        f"✅ <b>{user.name}</b> уже одобрен.\n\n"
        f"Роль: {ROLE_LABEL[UserRole.SUPERVISOR]}\n"
        "Привязанные склады:\n"
        f"{store_lines}",
    )

    try:
        await bot.send_message(
            user.telegram_id,
            f"🎉 <b>Вам выдан доступ!</b>\n\n"
            f"Роль: {ROLE_LABEL[UserRole.SUPERVISOR]}\n"
            "Доступные склады:\n"
            f"{store_lines}\n\n"
            "Нажмите /start чтобы начать работу.",
        )
    except Exception:
        logger.warning(
            "Could not notify approved supervisor tg_id={tg_id}",
            tg_id=user.telegram_id,
        )
