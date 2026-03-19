"""Role-based access middleware.

Injects `bot_user` (BotUser | None) into handler data.
Blocks unapproved users from accessing anything except /start and registration.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware
from loguru import logger
from sqlalchemy import select

from app.core.config import settings
from app.db.models.bot_user import BotUser, UserRole

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiogram.types import TelegramObject
    from sqlalchemy.ext.asyncio import async_sessionmaker


# Callback prefixes that don't require approval
_OPEN_PREFIXES = frozenset({"reg:", "adm_apr:", "adm_role:"})


class RoleAccessMiddleware(BaseMiddleware):
    """Check user role and inject `bot_user` into handler data."""

    def __init__(self, session_pool: async_sessionmaker) -> None:
        super().__init__()
        self.session_pool = session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Extract telegram user from the event
        tg_user = data.get("event_from_user")
        if not tg_user:
            return await handler(event, data)

        tg_id: int = tg_user.id

        # Auto-approve admin on first visit
        async with self.session_pool() as session:
            result = await session.execute(
                select(BotUser).where(BotUser.telegram_id == tg_id),
            )
            bot_user = result.scalar_one_or_none()

            if not bot_user and tg_id == settings.admin_telegram_id:
                bot_user = BotUser(
                    telegram_id=tg_id,
                    name="Admin",
                    role=UserRole.ADMIN,
                )
                session.add(bot_user)
                await session.commit()

        data["bot_user"] = bot_user

        # --- Extract text / callback_data from the Update ---
        # At update level, event is an Update object, not Message/CallbackQuery
        text = ""
        callback_data_raw = ""

        # event is an Update — get the inner message or callback_query
        message = getattr(event, "message", None)
        callback_query = getattr(event, "callback_query", None)

        if message and hasattr(message, "text") and message.text:
            text = message.text
        if callback_query and hasattr(callback_query, "data") and callback_query.data:
            callback_data_raw = callback_query.data

        # Always allow /start
        if text.startswith("/start"):
            return await handler(event, data)

        # Always allow registration & admin approval callbacks
        if any(callback_data_raw.startswith(p) for p in _OPEN_PREFIXES):
            return await handler(event, data)

        # If user has an FSM state active, allow text messages
        # (they're in the middle of a form like registration)
        fsm_context = data.get("state")
        if fsm_context:
            current_state = await fsm_context.get_state()
            if current_state:
                return await handler(event, data)

        # Block unapproved users
        if not bot_user or not bot_user.is_approved:
            logger.debug(
                "Blocked unapproved user tg_id={tg_id}",
                tg_id=tg_id,
            )
            return None

        return await handler(event, data)
