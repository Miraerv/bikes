"""Read-only model for boom_shift_couriers (existing table)."""

from datetime import datetime  # noqa: TC003

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MarketBase


class CourierShift(MarketBase):
    """Courier shift — boom_shift_couriers table.

    Created by external system. Bot reads to find active shifts.
    """

    __tablename__ = "boom_shift_couriers"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    admin_user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    store_ids: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(255), nullable=False)
    courier_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shift_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    shift_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    auto_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    def __repr__(self) -> str:
        return (
            f"<CourierShift(id={self.id}, admin_user_id={self.admin_user_id}, "
            f"status={self.status!r})>"
        )
