from concurrent.futures import ThreadPoolExecutor

from fastapi import HTTPException
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import Booking, IdempotencyRecord
from app.schemas import BookingCreate
from app.services.booking_service import create_booking_result


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

    with SessionLocal() as db:
        confirmed_count = db.scalar(
            select(func.count()).select_from(Booking).where(
                Booking.slot_id == "slot-concurrency",
                Booking.status == "confirmed",
            )
        )
    assert confirmed_count == 1


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


def test_failed_idempotency_finalization_rolls_back_booking_and_allows_retry(client, monkeypatch):
    headers = {"X-API-Key": "test-api-key"}
    response = client.post(
        "/reset",
        json={
            "slots": [
                {"id": "slot-idem-failure", "provider": "Dr. Recovery", "start": "2030-12-10T09:00:00Z", "end": "2030-12-10T09:30:00Z"}
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200

    def fail_finalization(*args, **kwargs):
        raise RuntimeError("simulated failure after booking flush")

    monkeypatch.setattr("app.services.booking_service.store_idempotency_response", fail_finalization)
    payload = {
        "slot_id": "slot-idem-failure",
        "name": "Recovery Patient",
        "email": "recovery@example.com",
    }

    failed = client.post(
        "/bookings",
        json=payload,
        headers={**headers, "Idempotency-Key": "failure-retry-key"},
    )
    assert failed.status_code == 500

    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(Booking).where(Booking.slot_id == "slot-idem-failure")
        ) == 0
        assert db.scalar(
            select(func.count()).select_from(IdempotencyRecord).where(
                IdempotencyRecord.idempotency_key == "failure-retry-key"
            )
        ) == 0

    monkeypatch.undo()
    retried = client.post(
        "/bookings",
        json=payload,
        headers={**headers, "Idempotency-Key": "failure-retry-key"},
    )
    assert retried.status_code == 201

    replayed = client.post(
        "/bookings",
        json=payload,
        headers={**headers, "Idempotency-Key": "failure-retry-key"},
    )
    assert replayed.status_code == 201
    assert replayed.json()["id"] == retried.json()["id"]

    with SessionLocal() as db:
        assert db.scalar(
            select(func.count()).select_from(Booking).where(Booking.slot_id == "slot-idem-failure")
        ) == 1
        record = db.scalar(
            select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == "failure-retry-key")
        )
        assert record is not None
        assert record.response_status == 201
        assert record.response_body
