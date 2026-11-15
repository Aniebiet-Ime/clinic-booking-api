from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_api_key
from app.schemas import BookingCreate, BookingHistoryResponse, BookingResponse
from app.services.booking_service import (
    cancel_booking,
    create_booking_result,
    get_booking_by_id,
    list_bookings_by_email,
    serialize_booking,
)

router = APIRouter(tags=["bookings"])


@router.post("/bookings")
def create_booking_endpoint(
    payload: BookingCreate,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_api_key),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    response_body, status_code = create_booking_result(db, payload, idempotency_key=idempotency_key)
    return JSONResponse(content=response_body, status_code=status_code)


@router.get("/bookings/{booking_id}")
def get_booking_endpoint(
    booking_id: str,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_api_key),
):
    booking = get_booking_by_id(db, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    return serialize_booking(booking)


@router.get("/bookings")
def list_bookings_endpoint(
    email: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
    cursor: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_api_key),
):
    if not email or not email.strip():
        raise HTTPException(status_code=400, detail="Email is required")
    return list_bookings_by_email(db, email=email, limit=limit, cursor=cursor)


@router.delete("/bookings/{booking_id}")
def delete_booking_endpoint(
    booking_id: str,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_api_key),
):
    return cancel_booking(db, booking_id)
