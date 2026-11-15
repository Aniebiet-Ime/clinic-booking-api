from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Slot(Base):
    __tablename__ = "slots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    bookings: Mapped[List["Booking"]] = relationship(back_populates="slot", cascade="all, delete-orphan")


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: f"booking-{uuid.uuid4().hex[:8]}")
    slot_id: Mapped[str] = mapped_column(ForeignKey("slots.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    slot: Mapped["Slot"] = relationship(back_populates="bookings")

    __table_args__ = (
        Index(
            "uq_confirmed_booking_slot",
            "slot_id",
            unique=True,
            sqlite_where=text("status = 'confirmed'"),
            postgresql_where=text("status = 'confirmed'"),
        ),
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: f"idem-{uuid.uuid4().hex[:12]}")
    idempotency_key: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    request_fingerprint: Mapped[str] = mapped_column(String, nullable=False)
    response_body: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )


class BookingAttempt(Base):
    __tablename__ = "booking_attempts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: f"attempt-{uuid.uuid4().hex[:12]}")
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
