from typing import ClassVar

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MarketBase


class Store(MarketBase):
    """Read-only model for boom_stores (existing table)."""

    __tablename__ = "boom_stores"
    __table_args__: ClassVar[dict[str, bool]] = {"extend_existing": True}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    main_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    @property
    def display_name(self) -> str:
        """Return street as display name, fallback to title."""
        return self.street or self.title
