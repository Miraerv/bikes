from datetime import datetime  # noqa: TC003 — SQLAlchemy needs at runtime
from enum import StrEnum

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MarketBase


class UserRole(StrEnum):
    """Roles for bike bot users."""

    ADMIN = "admin"
    SUPERVISOR = "supervisor"
    MECHANIC = "mechanic"
    COURIER = "courier"
    PENDING = "pending"


ROLE_LABEL: dict[str, str] = {
    "admin": "👑 Админ",
    "supervisor": "📋 Супервайзер",
    "mechanic": "🔧 Мастер",
    "courier": "🚚 Курьер",
    "pending": "⏳ Ожидает",
}


class BotUser(MarketBase):
    """Bike bot role record — boom_bike_bot_roles table.

    Stores telegram_id, name, admin_user_id (link to boom_admin_users), and role.
    Lives in boontar_market database.
    """

    __tablename__ = "boom_bike_bot_roles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(
        BigInteger, unique=True, index=True, nullable=False,
    )
    admin_user_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_supervisor(self) -> bool:
        return self.role == UserRole.SUPERVISOR

    @property
    def is_mechanic(self) -> bool:
        return self.role == UserRole.MECHANIC

    @property
    def is_courier(self) -> bool:
        return self.role == UserRole.COURIER

    @property
    def is_pending(self) -> bool:
        return self.role == UserRole.PENDING

    @property
    def is_approved(self) -> bool:
        return self.role in (
            UserRole.ADMIN, UserRole.SUPERVISOR,
            UserRole.MECHANIC, UserRole.COURIER,
        )

    @property
    def role_label(self) -> str:
        return ROLE_LABEL.get(self.role, self.role)

    def __repr__(self) -> str:
        return (
            f"<BotUser(id={self.id}, name={self.name!r}, "
            f"role={self.role!r}, tg={self.telegram_id})>"
        )
