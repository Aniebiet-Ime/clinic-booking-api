from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Booking, Slot
from app.schemas import BookingCreate
from app.services.booking_service import create_booking_result, get_available_slots

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
    normalized = email.strip().lower()
    rows = db.execute(
        select(Booking.id, Booking.slot_id, Booking.name, Booking.email, Booking.status, Booking.created_at, Slot.provider, Slot.start, Slot.end)
        .join(Slot, Slot.id == Booking.slot_id, isouter=True)
        .where(Booking.email == normalized)
        .order_by(Booking.created_at.asc(), Booking.id.asc())
    ).all()
    return {"bookings": [
        {
            "id": row.id,
            "slot_id": row.slot_id,
            "name": row.name,
            "email": row.email,
            "status": row.status,
            "provider": row.provider,
            "start": row.start.isoformat().replace("+00:00", "Z") if row.start else None,
            "end": row.end.isoformat().replace("+00:00", "Z") if row.end else None,
            "created_at": row.created_at.isoformat().replace("+00:00", "Z") if row.created_at else None,
        }
        for row in rows
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
    response_body, status_code = create_booking_result(db, payload)
    return JSONResponse(content=response_body, status_code=status_code)
