from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select

from app.core.config import settings
from app.db.models.bot_user import BotUser, UserRole

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def is_admin_actor(bot_user: BotUser | None, telegram_id: int) -> bool:
    """Return True for fallback admin id or users with admin role."""
    return telegram_id == settings.admin_telegram_id or (
        bot_user is not None and bot_user.is_admin
    )


async def get_admin_telegram_ids(session: AsyncSession) -> list[int]:
    """Return unique admin telegram ids including the fallback admin id."""
    result = await session.execute(
        select(BotUser.telegram_id)
        .where(BotUser.role == UserRole.ADMIN)
        .order_by(BotUser.id),
    )

    recipients = [row[0] for row in result.all()]
    recipients.append(settings.admin_telegram_id)

    unique_recipients: list[int] = []
    seen: set[int] = set()
    for telegram_id in recipients:
        if telegram_id in seen:
            continue
        seen.add(telegram_id)
        unique_recipients.append(telegram_id)

    return unique_recipients
