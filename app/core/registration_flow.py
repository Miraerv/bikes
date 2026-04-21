from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.core.admin_user_lookup import find_admin_user_by_phone
from app.core.display import MISSING_LABEL
from app.db.models.bot_user import ROLE_LABEL, BotUser, UserRole

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.models.admin_user import AdminUser


@dataclass(frozen=True)
class RegistrationApplication:
    bot_user: BotUser
    name: str
    phone_raw: str


def admin_user_registration_name(admin_user: AdminUser) -> str:
    surname = f" {admin_user.surname}" if admin_user.surname else ""
    name = f"{admin_user.name}{surname}"
    return name if name.strip() else MISSING_LABEL


async def create_registration_application(
    session: AsyncSession,
    *,
    telegram_id: int,
    phone_raw: str,
) -> RegistrationApplication | None:
    """Resolve an admin-panel user and create a pending bot registration."""
    admin_user = await find_admin_user_by_phone(session, phone_raw)
    if admin_user is None:
        return None

    name = admin_user_registration_name(admin_user)
    bot_user = BotUser(
        telegram_id=telegram_id,
        admin_user_id=admin_user.id,
        name=name,
        role=UserRole.PENDING,
    )
    session.add(bot_user)
    await session.flush()

    return RegistrationApplication(
        bot_user=bot_user,
        name=name,
        phone_raw=phone_raw,
    )


def assign_role(user: BotUser, role: str) -> str:
    user.role = role
    user.store_ids = None
    return ROLE_LABEL.get(role, role)


def assign_supervisor_role(user: BotUser, store_ids: list[int]) -> str:
    user.role = UserRole.SUPERVISOR
    user.set_assigned_store_ids(store_ids)
    return ROLE_LABEL[UserRole.SUPERVISOR]
