from datetime import datetime  # noqa: TC003 — SQLAlchemy needs at runtime

from sqlalchemy import BigInteger, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MarketBase


class BikeUsageLog(MarketBase):
    """Usage log — boom_bike_usage_logs."""

    __tablename__ = "boom_bike_usage_logs"

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
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # — Relationships —
    bike: Mapped[Bike] = relationship(back_populates="usage_logs", lazy="selectin")  # noqa: F821
    courier: Mapped[AdminUser] = relationship(  # noqa: F821
        foreign_keys=[courier_id], lazy="selectin",
    )
    store: Mapped[Store] = relationship(lazy="selectin")  # noqa: F821

    def __repr__(self) -> str:
        return (
            f"<BikeUsageLog(id={self.id}, bike_id={self.bike_id}, "
            f"courier_id={self.courier_id})>"
        )
