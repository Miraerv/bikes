"""Keyboard builders for registration and admin approval flows."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from app.bot.keyboards.callbacks import (
    AdminApprovalCB,
    AdminRoleSelectCB,
    AdminSupervisorStoreActionCB,
    AdminSupervisorStoreCB,
    RegistrationCB,
)

if TYPE_CHECKING:
    from app.db.models.store import Store


def registration_apply_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📝 Отправить заявку",
            callback_data=RegistrationCB(action="apply").pack(),
        )],
    ])


def registration_share_contact_kb() -> ReplyKeyboardMarkup:
    """Reply keyboard with 'Share contact' button."""
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Поделиться номером", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def admin_approval_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить",
                callback_data=AdminApprovalCB(
                    user_id=user_id,
                    action="approve",
                ).pack(),
            ),
            InlineKeyboardButton(
                text="❌ Отклонить",
                callback_data=AdminApprovalCB(
                    user_id=user_id,
                    action="reject",
                ).pack(),
            ),
        ],
    ])


def admin_role_select_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="👑 Админ",
            callback_data=AdminRoleSelectCB(
                user_id=user_id,
                role="admin",
            ).pack(),
        )],
        [InlineKeyboardButton(
            text="📋 Супервайзер",
            callback_data=AdminRoleSelectCB(
                user_id=user_id,
                role="supervisor",
            ).pack(),
        )],
        [InlineKeyboardButton(
            text="🔧 Мастер",
            callback_data=AdminRoleSelectCB(
                user_id=user_id,
                role="mechanic",
            ).pack(),
        )],
        [InlineKeyboardButton(
            text="🚚 Курьер",
            callback_data=AdminRoleSelectCB(
                user_id=user_id,
                role="courier",
            ).pack(),
        )],
    ])


def admin_supervisor_store_kb(
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
