from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi import HTTPException
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Booking
from app.schemas import BookingCreate
from app.services.booking_service import create_booking_result


def test_same_key_with_different_payload_is_rejected_concurrently(client):
    headers = {"X-API-Key": "test-api-key"}
    client.post(
        "/reset",
        json={
            "slots": [
                {"id": "slot-different-key", "provider": "Dr. Example", "start": "2030-12-10T09:00:00Z", "end": "2030-12-10T09:30:00Z"}
            ]
        },
        headers=headers,
    )

    barrier = Barrier(2)

    def attempt(name: str):
        db = SessionLocal()
        try:
            barrier.wait()
            payload = BookingCreate(
                slot_id="slot-different-key",
                name=name,
                email="ada@example.com",
            )
            try:
                body, status = create_booking_result(db, payload, idempotency_key="key-1")
                return status, body
            except HTTPException as exc:
                return exc.status_code, None
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["Ada", "Ada Changed"]))

    assert sorted(status for status, _ in results) == [201, 422]
    with SessionLocal() as db:
        confirmed_count = db.scalar(
            select(func.count()).select_from(Booking).where(
                Booking.slot_id == "slot-different-key",
                Booking.status == "confirmed",
            )
        )
    assert confirmed_count == 1


def test_idempotent_replay_returns_original_booking(client):
    headers = {"X-API-Key": "test-api-key"}
    client.post(
        "/reset",
        json={
            "slots": [
                {"id": "slot-idem-replay", "provider": "Dr. Replay", "start": "2030-12-11T09:00:00Z", "end": "2030-12-11T09:30:00Z"}
            ]
        },
        headers=headers,
    )

    first = client.post(
        "/bookings",
        json={"slot_id": "slot-idem-replay", "name": "Replay Patient", "email": "replay@example.com"},
        headers={**headers, "Idempotency-Key": "replay-key"},
    )
    assert first.status_code == 201
    second = client.post(
        "/bookings",
        json={"slot_id": "slot-idem-replay", "name": "Replay Patient", "email": "replay@example.com"},
        headers={**headers, "Idempotency-Key": "replay-key"},
    )
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]


def test_idempotency_rejects_mismatched_payload(client):
    headers = {"X-API-Key": "test-api-key"}
    client.post(
        "/reset",
        json={
            "slots": [
                {"id": "slot-mismatch", "provider": "Dr. Mismatch", "start": "2030-12-12T09:00:00Z", "end": "2030-12-12T09:30:00Z"}
            ]
        },
        headers=headers,
    )

    first = client.post(
        "/bookings",
        json={"slot_id": "slot-mismatch", "name": "Mismatch User", "email": "mismatch@example.com"},
        headers={**headers, "Idempotency-Key": "mismatched-key"},
    )
    assert first.status_code == 201

    second = client.post(
        "/bookings",
        json={"slot_id": "slot-mismatch", "name": "Different User", "email": "mismatch@example.com"},
        headers={**headers, "Idempotency-Key": "mismatched-key"},
    )
    assert second.status_code == 422
