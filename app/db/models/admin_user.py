from typing import ClassVar

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MarketBase


class AdminUser(MarketBase):
    """Read-only model for boom_admin_users (existing table)."""

    __tablename__ = "boom_admin_users"
    __table_args__: ClassVar[dict[str, bool]] = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    surname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)

    @property
    def display_name(self) -> str:
        """Format: 'Name Surname • 📱 phone'."""
        parts = [self.name]
        if self.surname:
            parts.append(self.surname)
        label = " ".join(parts)
        if self.phone:
            label += f" • 📱 {self.phone}"
        return label
