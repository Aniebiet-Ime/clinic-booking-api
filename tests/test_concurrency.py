import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException

from app.database import SessionLocal
from app.schemas import BookingCreate
from app.services.booking_service import create_booking_result


pytestmark = pytest.mark.skipif(
    os.getenv("DATABASE_URL", "").startswith("sqlite"),
    reason="PostgreSQL is required for transaction and uniqueness validation tests.",
)


def test_two_patients_cannot_book_same_slot_concurrently(client):
    headers = {"X-API-Key": "test-api-key"}
    response = client.post(
        "/reset",
        json={
            "slots": [
                {"id": "slot-concurrency", "provider": "Dr. Shared", "start": "2030-12-08T09:00:00Z", "end": "2030-12-08T09:30:00Z"}
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200

    def attempt(name: str, email: str):
        db = SessionLocal()
        try:
            payload = BookingCreate(slot_id="slot-concurrency", name=name, email=email)
            try:
                body, status = create_booking_result(db, payload)
                return {"status": status, "body": body}
            except HTTPException as exc:
                return {"status": exc.status_code, "detail": exc.detail}
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: attempt(*args), [("Ada Mint", "ada@example.com"), ("Ben Stone", "ben@example.com")]))

    statuses = {result["status"] for result in results}
    assert statuses == {201, 409}
    assert sum(1 for item in results if item["status"] == 201) == 1

    bookings = client.get("/bookings?email=ada@example.com", headers=headers)
    assert bookings.status_code == 200
    assert len(bookings.json()["bookings"]) == 1


def test_concurrent_same_idempotency_key_is_replayed_without_duplicate_booking(client):
    headers = {"X-API-Key": "test-api-key"}
    response = client.post(
        "/reset",
        json={
            "slots": [
                {"id": "slot-idem", "provider": "Dr. Retry", "start": "2030-12-09T09:00:00Z", "end": "2030-12-09T09:30:00Z"}
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200

    def attempt():
        db = SessionLocal()
        try:
            payload = BookingCreate(slot_id="slot-idem", name="Retry Patient", email="retry@example.com")
            body, status = create_booking_result(db, payload, idempotency_key="same-key")
            return {"status": status, "body": body}
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))

    assert all(item["status"] == 201 for item in results)
    booking_ids = {item["body"]["id"] for item in results}
    assert len(booking_ids) == 1
    assert len({item["body"]["slot_id"] for item in results}) == 1

    bookings = client.get("/bookings?email=retry@example.com", headers=headers)
    assert bookings.status_code == 200
    assert len(bookings.json()["bookings"]) == 1
