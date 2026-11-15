from __future__ import annotations


def test_provider_filter_returns_only_matching_slots(client):
    headers = {"X-API-Key": "test-api-key"}
    payload = {
        "slots": [
            {"id": "slot-001", "provider": "Dr. Ada", "start": "2030-12-01T09:00:00Z", "end": "2030-12-01T09:30:00Z"},
            {"id": "slot-002", "provider": "Dr. Ben", "start": "2030-12-01T10:00:00Z", "end": "2030-12-01T10:30:00Z"},
        ]
    }

    response = client.post("/reset", json=payload, headers=headers)
    assert response.status_code == 200

    filtered = client.get("/slots?provider=Dr. Ada", headers=headers)
    assert filtered.status_code == 200
    data = filtered.json()["slots"]
    assert len(data) == 1
    assert data[0]["provider"] == "Dr. Ada"
    assert data[0]["available"] is True


def test_availability_changes_after_booking_and_cancellation(client):
    headers = {"X-API-Key": "test-api-key"}
    client.post(
        "/reset",
        json={
            "slots": [
                {"id": "slot-100", "provider": "Dr. Clara", "start": "2030-12-03T09:00:00Z", "end": "2030-12-03T09:30:00Z"}
            ]
        },
        headers=headers,
    )

    slots_before = client.get("/slots", headers=headers)
    assert slots_before.json()["slots"][0]["available"] is True

    booking = client.post(
        "/bookings",
        json={"slot_id": "slot-100", "name": "Mina Joe", "email": "mina@example.com"},
        headers=headers,
    )
    assert booking.status_code == 201

    slots_after_booking = client.get("/slots", headers=headers)
    assert slots_after_booking.json()["slots"][0]["available"] is False

    cancellation = client.delete(f"/bookings/{booking.json()['id']}", headers=headers)
    assert cancellation.status_code == 200

    slots_after_cancel = client.get("/slots", headers=headers)
    assert slots_after_cancel.json()["slots"][0]["available"] is True


def test_past_slot_is_rejected(client):
    headers = {"X-API-Key": "test-api-key"}
    response = client.post(
        "/reset",
        json={
            "slots": [
                {"id": "past-slot", "provider": "Dr. Doe", "start": "2020-01-01T09:00:00Z", "end": "2020-01-01T09:30:00Z"}
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200

    booking = client.post(
        "/bookings",
        json={"slot_id": "past-slot", "name": "Past Patient", "email": "past@example.com"},
        headers=headers,
    )
    assert booking.status_code == 400
    assert "already started" in booking.json()["error"].lower()


def test_reset_repopulates_slots(client):
    headers = {"X-API-Key": "test-api-key"}
    first = {"slots": [{"id": "slot-a", "provider": "Dr. A", "start": "2030-12-04T09:00:00Z", "end": "2030-12-04T09:30:00Z"}]}
    second = {"slots": [{"id": "slot-b", "provider": "Dr. B", "start": "2030-12-04T10:00:00Z", "end": "2030-12-04T10:30:00Z"}]}

    assert client.post("/reset", json=first, headers=headers).status_code == 200
    assert client.get("/slots", headers=headers).json()["slots"][0]["id"] == "slot-a"

    assert client.post("/reset", json=second, headers=headers).status_code == 200
    data = client.get("/slots", headers=headers).json()["slots"]
    assert [slot["id"] for slot in data] == ["slot-b"]
