import os

import pytest

from app.models import IdempotencyRecord


@pytest.mark.skipif(
    os.getenv("DATABASE_URL", "").startswith("sqlite"),
    reason="PostgreSQL is required for concurrent idempotency collision tests.",
)
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

    response = client.post(
        "/bookings",
        json={"slot_id": "slot-different-key", "name": "Ada", "email": "ada@example.com"},
        headers={**headers, "Idempotency-Key": "key-1"},
    )
    assert response.status_code == 201

    mismatched = client.post(
        "/bookings",
        json={"slot_id": "slot-different-key", "name": "Ada Changed", "email": "ada@example.com"},
        headers={**headers, "Idempotency-Key": "key-1"},
    )
    assert mismatched.status_code == 422


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


def test_incomplete_idempotency_record_is_rejected(client):
    from app.database import SessionLocal

    from app.services.idempotency import request_fingerprint

    session = SessionLocal()
    try:
        payload = {"slot_id": "slot-999", "name": "Broken", "email": "broken@example.com"}
        record = IdempotencyRecord(
            idempotency_key="incomplete-key",
            request_fingerprint=request_fingerprint(payload),
            response_body="",
            response_status=0,
        )
        session.add(record)
        session.commit()

        headers = {"X-API-Key": "test-api-key"}
        response = client.post(
            "/bookings",
            json=payload,
            headers={**headers, "Idempotency-Key": "incomplete-key"},
        )
        assert response.status_code == 500
    finally:
        session.close()
