import enum
from datetime import date, datetime  # noqa: TC003 — SQLAlchemy needs at runtime

from sqlalchemy import BigInteger, Date, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MarketBase


class BikeStatus(enum.StrEnum):
    """Bike status enum matching the DB column."""

    ONLINE = "online"
    INSPECTION = "inspection"
    REPAIR = "repair"
    DECOMMISSIONED = "decommissioned"


class Bike(MarketBase):
    """Bike registry — boom_bikes."""

    __tablename__ = "boom_bikes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bike_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    commissioned_at: Mapped[date] = mapped_column(Date, nullable=False)
    store_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boom_stores.id"), nullable=False,
    )
    status: Mapped[BikeStatus] = mapped_column(
        Enum(BikeStatus, values_callable=lambda e: [x.value for x in e]),
        nullable=False,
        default=BikeStatus.ONLINE,
        server_default="online",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # — Relationships —
    store: Mapped[Store] = relationship(lazy="selectin")  # noqa: F821
    usage_logs: Mapped[list[BikeUsageLog]] = relationship(  # noqa: F821
        back_populates="bike", cascade="all, delete-orphan",
    )
    breakdowns: Mapped[list[BikeBreakdown]] = relationship(  # noqa: F821
        back_populates="bike", cascade="all, delete-orphan",
    )
    repairs: Mapped[list[BikeRepair]] = relationship(  # noqa: F821
        back_populates="bike", cascade="all, delete-orphan",
    )
    alerts: Mapped[list[BikeAlert]] = relationship(  # noqa: F821
        back_populates="bike", cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Bike(id={self.id}, number={self.bike_number!r}, status={self.status.value})>"
