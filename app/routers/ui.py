from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import BookingCreate
from app.services.booking_service import create_booking, get_available_slots

router = APIRouter(prefix="/api/ui", tags=["ui"])


@router.get("/slots")
def ui_get_slots(
    provider: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return {"slots": get_available_slots(db, provider=provider)}


@router.get("/bookings")
def ui_get_bookings(
    email: str,
    db: Session = Depends(get_db),
):
    from app.models import Booking
    from sqlalchemy import select

    normalized = email.strip().lower()
    rows = db.execute(
        select(Booking).where(Booking.email == normalized).order_by(Booking.created_at.asc(), Booking.id.asc())
    ).scalars().all()
    return {"bookings": [
        {
            "id": booking.id,
            "slot_id": booking.slot_id,
            "name": booking.name,
            "email": booking.email,
            "status": booking.status,
            "created_at": booking.created_at.isoformat().replace("+00:00", "Z"),
        }
        for booking in rows
    ]}


@router.post("/bookings")
def ui_create_booking(
    booking_data: dict,
    db: Session = Depends(get_db),
):
    try:
        payload = BookingCreate.model_validate(booking_data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()[0].get("msg", "Invalid booking data")) from exc
    return create_booking(db, payload)
