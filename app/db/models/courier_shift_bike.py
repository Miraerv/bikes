"""Model for boom_shift_couriers_bike table."""

from datetime import datetime  # noqa: TC003

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import MarketBase


class CourierShiftBike(MarketBase):
    """Bike record within a courier shift — boom_shift_couriers_bike table.

    type='start' — courier took the bike
    type='end'   — courier returned the bike
    """

    __tablename__ = "boom_shift_couriers_bike"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    shift_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("boom_shift_couriers.id", ondelete="CASCADE"),
        nullable=False,
    )
    photo_url: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    checklist: Mapped[str] = mapped_column(String(2000), nullable=False, default="{}")
    bike_number: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False, default="start")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<CourierShiftBike(id={self.id}, shift_id={self.shift_id}, "
            f"bike_number={self.bike_number!r}, type={self.type!r})>"
        )
