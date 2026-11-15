from __future__ import annotations


def test_reset_and_list_slots(client):
    headers = {"X-API-Key": "test-api-key"}
    payload = {
        "slots": [
            {"id": "slot-001", "provider": "Dr. John", "start": "2026-12-01T09:00:00Z", "end": "2026-12-01T09:30:00Z"},
            {"id": "slot-002", "provider": "Dr. Jane", "start": "2026-12-01T10:00:00Z", "end": "2026-12-01T10:30:00Z"},
        ]
    }
    response = client.post("/reset", json=payload, headers=headers)
    assert response.status_code == 200
    slots = client.get("/slots", headers=headers)
    assert slots.status_code == 200
    data = slots.json()["slots"]
    assert len(data) == 2
    assert data[0]["available"] is True
    assert data[0]["provider"] == "Dr. John"


def test_book_and_get_booking(client):
    headers = {"X-API-Key": "test-api-key"}
    client.post("/reset", json={"slots": [{"id": "slot-001", "provider": "Dr. John", "start": "2030-12-01T09:00:00Z", "end": "2030-12-01T09:30:00Z"}]}, headers=headers)

    booking = client.post(
        "/bookings",
        json={"slot_id": "slot-001", "name": "Ada Obi", "email": "ADA@example.com"},
        headers=headers,
    )
    assert booking.status_code == 201
    payload = booking.json()
    assert payload["email"] == "ada@example.com"
    assert payload["status"] == "confirmed"

    fetched = client.get(f"/bookings/{payload['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["slot_id"] == "slot-001"


def test_booking_validation_and_api_key(client):
    headers = {"X-API-Key": "invalid-key"}
    response = client.post(
        "/bookings",
        json={"slot_id": "slot-001", "name": "Ada", "email": "invalid-email"},
        headers=headers,
    )
    assert response.status_code == 401

    valid_headers = {"X-API-Key": "test-api-key"}
    client.post("/reset", json={"slots": [{"id": "slot-001", "provider": "Dr. John", "start": "2030-12-01T09:00:00Z", "end": "2030-12-01T09:30:00Z"}]}, headers=valid_headers)
    response = client.post(
        "/bookings",
        json={"slot_id": "slot-001", "name": "", "email": "ada@example.com"},
        headers=valid_headers,
    )
    assert response.status_code == 400


def test_idempotent_retry(client):
    headers = {"X-API-Key": "test-api-key"}
    client.post("/reset", json={"slots": [{"id": "slot-001", "provider": "Dr. John", "start": "2030-12-01T09:00:00Z", "end": "2030-12-01T09:30:00Z"}]}, headers=headers)

    response = client.post(
        "/bookings",
        json={"slot_id": "slot-001", "name": "Ada Obi", "email": "ada@example.com"},
        headers={**headers, "Idempotency-Key": "abc-123"},
    )
    assert response.status_code == 201
    replay = client.post(
        "/bookings",
        json={"slot_id": "slot-001", "name": "Ada Obi", "email": "ada@example.com"},
        headers={**headers, "Idempotency-Key": "abc-123"},
    )
    assert replay.status_code == 201
    assert replay.json()["id"] == response.json()["id"]
