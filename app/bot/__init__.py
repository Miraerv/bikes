from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Dispatcher
from aiogram.exceptions import TelegramBadRequest
from loguru import logger

if TYPE_CHECKING:
    from aiogram.types import ErrorEvent

from app.bot.handlers import router as main_router
from app.db.base import market_session_maker
from app.middlewares.db import DbSessionMiddleware
from app.middlewares.role_access import RoleAccessMiddleware


def create_dispatcher() -> Dispatcher:
    """Build and configure the Dispatcher with all routers and middleware."""
    dp = Dispatcher()

    # Register middleware — all sessions use market DB now
    dp.update.middleware(
        DbSessionMiddleware(
            market_session_pool=market_session_maker,
        ),
    )
    dp.update.middleware(
        RoleAccessMiddleware(session_pool=market_session_maker),
    )

    # Include routers
    dp.include_router(main_router)

    # Global error handler — suppress "message is not modified" (double-tap)
    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        ex = event.exception
        if isinstance(ex, TelegramBadRequest) and "message is not modified" in str(ex):
            logger.debug("Suppressed: message is not modified (double-tap)")
            return True
        return False

    return dp
