"""Handle /start — authorization only, /menu — role-aware menu."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router
from aiogram.filters import Command, CommandStart
from loguru import logger

from app.bot.keyboards.builders import courier_menu_kb, main_menu_kb
from app.bot.keyboards.registration import registration_apply_kb

if TYPE_CHECKING:
    from aiogram.types import Message

    from app.db.models.bot_user import BotUser

router = Router(name="start")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    bot_user: BotUser | None = None,
) -> None:
    """Handle /start — authorization / registration only."""
    if message.from_user is None:
        return

    tg_user = message.from_user
    logger.info("User started bot: {telegram_id}", telegram_id=tg_user.id)

    # Approved user → welcome + hint to use /menu
    if bot_user and bot_user.is_approved:
        await message.answer(
            f"👋 Привет, <b>{bot_user.name}</b>!\n"
            f"Роль: {bot_user.role_label}\n\n"
            "✅ Вы авторизованы.\n"
            "Для открытия меню нажмите /menu",
        )
        return

    # Pending user → waiting for approval
    if bot_user and bot_user.is_pending:
        await message.answer(
            f"⏳ Привет, <b>{bot_user.name}</b>!\n\n"
            "Ваша заявка на рассмотрении.\n"
            "Ожидайте одобрения администратора.",
        )
        return

    # New user → offer to register
    await message.answer(
        f"👋 Привет, <b>{tg_user.first_name or 'друг'}</b>!\n\n"
        "Для работы с ботом нужен доступ.\n"
        "Отправьте заявку администратору:",
        reply_markup=registration_apply_kb(),
    )


@router.message(Command("menu"))
async def cmd_menu(
    message: Message,
    bot_user: BotUser | None = None,
) -> None:
    """Handle /menu — show main menu based on role."""
    if message.from_user is None:
        return

    # Not authorized
    if not bot_user or not bot_user.is_approved:
        await message.answer(
            "⛔ У вас нет доступа.\nНажмите /start для регистрации.",
        )
        return

    # Courier gets simplified menu
    if bot_user.is_courier:
        await message.answer(
            "🚚 <b>Меню курьера</b>\nВыберите действие:",
            reply_markup=courier_menu_kb(),
        )
    else:
        await message.answer(
            "🏠 <b>Главное меню</b>\nВыберите раздел:",
            reply_markup=main_menu_kb(),
        )
