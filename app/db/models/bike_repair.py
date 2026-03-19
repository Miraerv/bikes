from datetime import datetime  # noqa: TC003 — SQLAlchemy needs at runtime
from decimal import Decimal  # noqa: TC003

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MarketBase


class BikeRepair(MarketBase):
    """Repair record — boom_bike_repairs."""

    __tablename__ = "boom_bike_repairs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bike_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boom_bikes.id", ondelete="CASCADE"), nullable=False,
    )
    breakdown_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("boom_bike_breakdowns.id", ondelete="SET NULL"),
        nullable=True,
    )
    mechanic_id: Mapped[int | None] = mapped_column(
        BigInteger, nullable=True,
    )
    mechanic_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boom_stores.id"), nullable=False,
    )
    picked_up_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    work_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    repair_duration_minutes: Mapped[int | None] = mapped_column(
        Integer().with_variant(Integer, "mysql"), nullable=True,
    )
    cost: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # — Relationships —
    bike: Mapped[Bike] = relationship(back_populates="repairs", lazy="selectin")  # noqa: F821
    breakdown: Mapped[BikeBreakdown | None] = relationship(  # noqa: F821
        back_populates="repairs", lazy="selectin",
    )
    store: Mapped[Store] = relationship(lazy="selectin")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<BikeRepair(id={self.id}, bike_id={self.bike_id}, "
            f"mechanic={self.mechanic_name})>"
        )
