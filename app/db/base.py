from sqlalchemy.ext.asyncio import (
    AsyncAttrs,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# — Market database (single DB for everything) —
market_engine = create_async_engine(
    settings.database_url_market,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
)

market_session_maker = async_sessionmaker(
    market_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class MarketBase(AsyncAttrs, DeclarativeBase):
    """Declarative base for all models (boontar_market database)."""
