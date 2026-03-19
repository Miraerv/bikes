"""Registration & admin approval handlers (Stage 9 — Roles)."""

from __future__ import annotations

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
    RegistrationCB,
)
from app.bot.states.bike import RegistrationForm
from app.core.config import settings
from app.db.models.admin_user import AdminUser
from app.db.models.bot_user import ROLE_LABEL, BotUser, UserRole

if TYPE_CHECKING:
    from aiogram import Bot
    from aiogram.fsm.context import FSMContext
    from aiogram.types import CallbackQuery, Message
    from sqlalchemy.ext.asyncio import AsyncSession

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


def _normalize_phone(phone: str) -> str:
    """Strip everything except digits from a phone number."""
    return "".join(c for c in phone if c.isdigit())


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
    phone_variants = set()
    phone_variants.add(phone_digits)
    if phone_digits.startswith("7") and len(phone_digits) == 11:
        phone_variants.add("8" + phone_digits[1:])
        phone_variants.add("+" + phone_digits)
    elif phone_digits.startswith("8") and len(phone_digits) == 11:
        phone_variants.add("7" + phone_digits[1:])
        phone_variants.add("+7" + phone_digits[1:])

    admin_user = None
    for variant in phone_variants:
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
    await bot.send_message(
        settings.admin_telegram_id,
        f"🆕 <b>Новая заявка на доступ</b>\n\n"
        f"👤 Имя: <b>{name}</b>\n"
        f"📱 Телефон: <code>{phone_raw}</code>\n"
        f"💬 Telegram: {tg_link}",
        reply_markup=_approval_kb(bot_user.id),
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
) -> None:
    """Admin approves — show role selection."""
    if callback.from_user.id != settings.admin_telegram_id:
        await callback.answer("⛔️ Только администратор может одобрять заявки.")
        return

    await callback.answer()
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


@router.callback_query(AdminApprovalCB.filter(F.action == "reject"))
async def admin_reject(
    callback: CallbackQuery,
    callback_data: AdminApprovalCB,
    market_session: AsyncSession,
    bot: Bot,
) -> None:
    """Admin rejects the application."""
    if callback.from_user.id != settings.admin_telegram_id:
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
) -> None:
    """Admin assigns a specific role."""
    if callback.from_user.id != settings.admin_telegram_id:
        await callback.answer("⛔️ Только администратор.")
        return

    await callback.answer()
    user = await market_session.get(BotUser, callback_data.user_id)
    if not user:
        await callback.message.edit_text(  # type: ignore[union-attr]
            "⚠️ Пользователь не найден.",
        )
        return

    user.role = callback_data.role
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
