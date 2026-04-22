from __future__ import annotations

from datetime import datetime  # noqa: TC003 — SQLAlchemy needs at runtime

from sqlalchemy import BigInteger, DateTime, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MarketBase


class BotUserAdminNotification(MarketBase):
    """Tracks admin-facing Telegram messages for pending role requests."""

    __tablename__ = "boom_bike_bot_role_admin_notifications"
    __table_args__ = (
        UniqueConstraint(
            "bot_user_id",
            "admin_telegram_id",
            name="boom_bike_bot_role_admin_notifications_user_admin_unique",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_user_id: Mapped[int] = mapped_column(
        ForeignKey("boom_bike_bot_roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    admin_telegram_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        index=True,
    )
    message_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<BotUserAdminNotification(id={self.id}, user_id={self.bot_user_id}, "
            f"admin_tg={self.admin_telegram_id}, message_id={self.message_id})>"
        )
