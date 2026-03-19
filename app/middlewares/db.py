from __future__ import annotations

from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from aiogram.types import TelegramObject
    from sqlalchemy.ext.asyncio import async_sessionmaker


class DbSessionMiddleware(BaseMiddleware):
    """Inject AsyncSession for the market database into handler data."""

    def __init__(
        self,
        market_session_pool: async_sessionmaker,
    ) -> None:
        super().__init__()
        self.market_session_pool = market_session_pool

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with self.market_session_pool() as market_session:
            data["market_session"] = market_session
            try:
                result = await handler(event, data)
                await market_session.commit()
                return result
            except Exception:
                await market_session.rollback()
                raise
