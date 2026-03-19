import enum
from datetime import datetime  # noqa: TC003 — SQLAlchemy needs at runtime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MarketBase


class BreakdownType(enum.StrEnum):
    """Breakdown category enum."""

    BRAKES = "brakes"
    WHEEL = "wheel"
    BATTERY = "battery"
    MOTOR = "motor"
    FRAME = "frame"
    ELECTRONICS = "electronics"
    OTHER = "other"


class BikeBreakdown(MarketBase):
    """Breakdown card — boom_bike_breakdowns."""

    __tablename__ = "boom_bike_breakdowns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bike_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boom_bikes.id", ondelete="CASCADE"), nullable=False,
    )
    courier_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boom_admin_users.id"), nullable=False,
    )
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boom_stores.id"), nullable=False,
    )
    reported_by: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boom_admin_users.id"), nullable=False,
    )
    breakdown_type: Mapped[BreakdownType] = mapped_column(
        Enum(BreakdownType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # — Relationships —
    bike: Mapped[Bike] = relationship(back_populates="breakdowns", lazy="selectin")  # noqa: F821
    courier: Mapped[AdminUser] = relationship(  # noqa: F821
        foreign_keys=[courier_id], lazy="selectin",
    )
    reporter: Mapped[AdminUser] = relationship(  # noqa: F821
        foreign_keys=[reported_by], lazy="selectin",
    )
    store: Mapped[Store] = relationship(lazy="selectin")  # noqa: F821
    photos: Mapped[list[BikeBreakdownPhoto]] = relationship(  # noqa: F821
        back_populates="breakdown", cascade="all, delete-orphan",
    )
    repairs: Mapped[list[BikeRepair]] = relationship(  # noqa: F821
        back_populates="breakdown",
    )

    def __repr__(self) -> str:
        return (
            f"<BikeBreakdown(id={self.id}, bike_id={self.bike_id}, "
            f"type={self.breakdown_type.value})>"
        )
