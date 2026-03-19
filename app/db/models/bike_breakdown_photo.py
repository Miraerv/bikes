from datetime import datetime  # noqa: TC003 — SQLAlchemy needs at runtime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import MarketBase


class BikeBreakdownPhoto(MarketBase):
    """Photo evidence for a breakdown — boom_bike_breakdown_photos."""

    __tablename__ = "boom_bike_breakdown_photos"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    breakdown_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("boom_bike_breakdowns.id", ondelete="CASCADE"),
        nullable=False,
    )
    photo_url: Mapped[str] = mapped_column(String(500), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False,
    )

    # — Relationships —
    breakdown: Mapped[BikeBreakdown] = relationship(  # noqa: F821
        back_populates="photos", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<BikeBreakdownPhoto(id={self.id}, breakdown_id={self.breakdown_id})>"
