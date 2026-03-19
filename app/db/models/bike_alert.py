import enum
from datetime import datetime  # noqa: TC003 — SQLAlchemy needs at runtime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MarketBase


class AlertType(enum.StrEnum):
    """Alert type enum."""

    LOW_BIKES = "low_bikes"
    REPAIR_TOO_LONG = "repair_too_long"
    FREQUENT_BREAKDOWNS = "frequent_breakdowns"


class BikeAlert(MarketBase):
    """Alert notification — boom_bike_alerts."""

    __tablename__ = "boom_bike_alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bike_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("boom_bikes.id", ondelete="CASCADE"), nullable=True,
    )
    store_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("boom_stores.id", ondelete="SET NULL"), nullable=True,
    )
    alert_type: Mapped[AlertType] = mapped_column(
        Enum(AlertType, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # — Relationships —
    bike: Mapped[Bike | None] = relationship(  # noqa: F821
        back_populates="alerts", lazy="selectin",
    )
    store: Mapped[Store | None] = relationship(lazy="selectin")  # noqa: F821

    def __repr__(self) -> str:
        return f"<BikeAlert(id={self.id}, type={self.alert_type.value}, read={self.is_read})>"
