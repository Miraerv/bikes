from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import false, select

from app.core.config import settings
from app.db.models.store import Store

if TYPE_CHECKING:
    from aiogram.types import CallbackQuery
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import InstrumentedAttribute
    from sqlalchemy.sql import ColumnElement
    from sqlalchemy.sql.selectable import Select

    from app.db.models.bot_user import BotUser


def get_store_scope(bot_user: BotUser | None) -> list[int] | None:
    """Return restricted store ids for supervisors, or None for unrestricted access."""
    if bot_user is None or not bot_user.is_supervisor:
        return None

    if bot_user.store_ids is None:
        return None

    return bot_user.assigned_store_ids


def has_store_access(bot_user: BotUser | None, store_id: int) -> bool:
    """Check whether the current user may access the given store."""
    scope = get_store_scope(bot_user)
    return scope is None or store_id in scope


def apply_store_scope(
    stmt: Select[Any],
    store_column: ColumnElement[int] | InstrumentedAttribute[int],
    bot_user: BotUser | None,
) -> Select[Any]:
    """Restrict a SQLAlchemy statement to stores available for the user."""
    scope = get_store_scope(bot_user)
    if scope is None:
        return stmt
    if not scope:
        return stmt.where(false())
    return stmt.where(store_column.in_(scope))


async def get_accessible_stores(
    session: AsyncSession,
    bot_user: BotUser | None = None,
) -> list[Store]:
    """Load visible express stores for the current user."""
    stmt = (
        select(Store)
        .where(Store.main_id == "express", Store.id.notin_(settings.hidden_store_ids))
        .order_by(Store.street)
    )
    result = await session.execute(apply_store_scope(stmt, Store.id, bot_user))
    return list(result.scalars().all())


async def guard_store_access(
    callback: CallbackQuery,
    bot_user: BotUser | None,
    store_id: int,
) -> bool:
    """Answer the callback and block the flow when the store is not available."""
    if has_store_access(bot_user, store_id):
        return True

    await callback.answer("⛔️ У вас нет доступа к этому складу.")
    return False
