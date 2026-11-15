from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Booking, BookingAttempt, IdempotencyRecord, Slot
from app.schemas import BookingCreate
from app.services.idempotency import (
    acquire_idempotency_lock,
    delete_incomplete_idempotency_record,
    get_idempotency_record,
    request_fingerprint,
    store_idempotency_response,
)
from app.services.rate_limiter import can_attempt_booking, record_booking_attempt


def serialize_booking(booking: Booking) -> dict[str, Any]:
    created_at = ensure_utc(booking.created_at) or booking.created_at
    return {
        "id": booking.id,
        "slot_id": booking.slot_id,
        "name": booking.name,
        "email": booking.email,
        "status": booking.status,
        "created_at": created_at.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    }


def encode_cursor(value: datetime, booking_id: str) -> str:
    normalized = ensure_utc(value) or value
    token = f"{normalized.replace(tzinfo=None).isoformat()}|{booking_id}"
    return base64.urlsafe_b64encode(token.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    decoded = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    created_at_text, booking_id = decoded.split("|", 1)
    return datetime.fromisoformat(created_at_text).replace(tzinfo=None), booking_id


def ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError(f"Unsupported datetime value: {value!r}")
    return ensure_utc(result)


def reset_slots(db: Session, slots: list[dict[str, Any]]) -> dict[str, str]:
    with db.begin():
        db.query(Booking).delete()
        db.query(Slot).delete()
        for slot in slots:
            db.add(
                Slot(
                    id=slot["id"],
                    provider=slot["provider"],
                    start=parse_datetime(slot["start"]),
                    end=parse_datetime(slot["end"]),
                )
            )
    return {"status": "ok"}


def get_available_slots(db: Session, provider: str | None = None) -> list[dict[str, Any]]:
    query = select(Slot).order_by(Slot.start.asc(), Slot.id.asc())
    if provider:
        query = query.where(Slot.provider == provider)
    slots = db.execute(query).scalars().all()
    results = []
    for slot in slots:
        confirmed = db.execute(
            select(func.count(Booking.id)).where(
                and_(Booking.slot_id == slot.id, Booking.status == "confirmed")
            )
        ).scalar() or 0
        slot_start = ensure_utc(slot.start) or slot.start
        slot_end = ensure_utc(slot.end) or slot.end
        results.append(
            {
                "id": slot.id,
                "provider": slot.provider,
                "start": slot_start.astimezone(timezone.utc).replace(microsecond=0),
                "end": slot_end.astimezone(timezone.utc).replace(microsecond=0),
                "available": confirmed == 0,
            }
        )
    return results


def get_booking_by_id(db: Session, booking_id: str) -> Booking | None:
    return db.get(Booking, booking_id)


def _normalize_idempotency_key(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def create_booking(db: Session, payload: BookingCreate, idempotency_key: str | None = None) -> dict[str, Any]:
    response_body, _ = create_booking_result(db, payload, idempotency_key=idempotency_key)
    return response_body


def create_booking_result(db: Session, payload: BookingCreate, idempotency_key: str | None = None) -> tuple[dict[str, Any], int]:
    name = payload.name.strip()
    email = payload.email.strip().lower()
    fingerprint = request_fingerprint(payload.model_dump(mode="json"))
    key = _normalize_idempotency_key(idempotency_key)

    if key:
        acquire_idempotency_lock(db, key)
        existing = get_idempotency_record(db, key)
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise HTTPException(status_code=422, detail="Idempotency key reused with a different request body")
            if existing.response_status in (None, 0) or not existing.response_body:
                delete_incomplete_idempotency_record(db, key)
                raise HTTPException(status_code=500, detail="Idempotency response is still being finalized")
            return json.loads(existing.response_body), int(existing.response_status)

    allowed = True
    retry_after = 0
    allowed, retry_after = can_attempt_booking(db, email)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many booking attempts for this email; please retry later.",
            headers={"Retry-After": str(retry_after)},
        )

    record_booking_attempt(db, email)
    db.commit()

    try:
        with db.begin():
            if key:
                acquire_idempotency_lock(db, key)
                existing = get_idempotency_record(db, key)
                if existing is not None:
                    if existing.request_fingerprint != fingerprint:
                        raise HTTPException(status_code=422, detail="Idempotency key reused with a different request body")
                    if existing.response_status in (None, 0) or not existing.response_body:
                        raise HTTPException(status_code=500, detail="Idempotency response is still being finalized")
                    return json.loads(existing.response_body), int(existing.response_status)

                record = IdempotencyRecord(
                    id=f"idem-{uuid.uuid4().hex[:12]}",
                    idempotency_key=key,
                    request_fingerprint=fingerprint,
                    response_body="",
                    response_status=0,
                )
                db.add(record)
                db.flush()

            slot = db.get(Slot, payload.slot_id)
            if slot is None:
                raise HTTPException(status_code=404, detail="Slot not found")

            slot_start = ensure_utc(slot.start) or slot.start
            if slot_start <= datetime.now(timezone.utc):
                raise HTTPException(status_code=400, detail="Slot has already started")

            existing_confirmed = db.execute(
                select(Booking.id).where(and_(Booking.slot_id == slot.id, Booking.status == "confirmed"))
            ).scalar_one_or_none()
            if existing_confirmed is not None:
                raise HTTPException(status_code=409, detail="Slot is already booked")

            booking = Booking(
                id=f"booking-{uuid.uuid4().hex[:8]}",
                slot_id=slot.id,
                name=name,
                email=email,
                status="confirmed",
                created_at=datetime.now(timezone.utc),
            )
            db.add(booking)
            db.flush()
            response_body = serialize_booking(booking)

            if key:
                record = get_idempotency_record(db, key)
                if record is None:
                    raise HTTPException(status_code=500, detail="Idempotency record missing after booking creation")
                store_idempotency_response(db, record, response_body, 201)

            return response_body, 201
    except HTTPException:
        db.rollback()
        if key:
            delete_incomplete_idempotency_record(db, key)
        raise
    except IntegrityError:
        db.rollback()
        if key:
            delete_incomplete_idempotency_record(db, key)
            try:
                existing = get_idempotency_record(db, key)
                if existing is not None:
                    if existing.request_fingerprint != fingerprint:
                        raise HTTPException(status_code=422, detail="Idempotency key reused with a different request body")
                    if existing.response_body and existing.response_status not in (None, 0):
                        return json.loads(existing.response_body), int(existing.response_status)
            finally:
                db.rollback()
        else:
            db.rollback()
        raise HTTPException(status_code=409, detail="Slot is already booked")
    except Exception:
        db.rollback()
        if key:
            delete_incomplete_idempotency_record(db, key)
        raise


def list_bookings_by_email(db: Session, email: str, limit: int = 10, cursor: str | None = None) -> dict[str, Any]:
    normalized = email.strip().lower()
    query = select(Booking).where(Booking.email == normalized).order_by(Booking.created_at.asc(), Booking.id.asc())
    if cursor:
        last_created_at, last_id = decode_cursor(cursor)
        query = query.where(
            or_(
                Booking.created_at > last_created_at,
                and_(Booking.created_at == last_created_at, Booking.id > last_id),
            )
        )

    rows = db.execute(query.limit(limit + 1)).scalars().all()
    if len(rows) > limit:
        next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id)
        results = rows[:limit]
    else:
        next_cursor = None
        results = rows

    return {"bookings": [serialize_booking(item) for item in results], "next_cursor": next_cursor}


def cancel_booking(db: Session, booking_id: str) -> dict[str, Any]:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if booking.status == "cancelled":
        raise HTTPException(status_code=409, detail="Booking has already been cancelled")
    booking.status = "cancelled"
    db.add(booking)
    db.commit()
    return serialize_booking(booking)
