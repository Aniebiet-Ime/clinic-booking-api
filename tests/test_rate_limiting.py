import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import BookingAttempt
from app.services.rate_limiter import RATE_LIMIT_MAX_ATTEMPTS, RATE_LIMIT_WINDOW_SECONDS, can_attempt_booking


def test_first_five_attempts_are_allowed_and_sixth_is_429(client):
    headers = {"X-API-Key": "test-api-key"}
    slots = [
        {"id": f"rate-slot-{index}", "provider": f"Dr. Rate {index}", "start": f"2030-12-{(index + 1):02d}T09:00:00Z", "end": f"2030-12-{(index + 1):02d}T09:30:00Z"}
        for index in range(1, 7)
    ]
    client.post("/reset", json={"slots": slots}, headers=headers)

    for index in range(RATE_LIMIT_MAX_ATTEMPTS):
        response = client.post(
            "/bookings",
            json={"slot_id": f"rate-slot-{index + 1}", "name": f"User {index}", "email": "shared@example.com"},
            headers=headers,
        )
        assert response.status_code == 201, response.json()

    blocked = client.post(
        "/bookings",
        json={"slot_id": "rate-slot-6", "name": "User 6", "email": "shared@example.com"},
        headers=headers,
    )
    assert blocked.status_code == 429, blocked.json()
    assert blocked.headers["Retry-After"].isdigit()


def test_failed_attempts_and_different_emails_are_isolated(client):
    headers = {"X-API-Key": "test-api-key"}
    slots = [
        {"id": "rate-alpha-1", "provider": "Dr. Alpha 1", "start": "2030-12-21T09:00:00Z", "end": "2030-12-21T09:30:00Z"},
        {"id": "rate-alpha-2", "provider": "Dr. Alpha 2", "start": "2030-12-21T10:00:00Z", "end": "2030-12-21T10:30:00Z"},
        {"id": "rate-alpha-3", "provider": "Dr. Alpha 3", "start": "2030-12-21T11:00:00Z", "end": "2030-12-21T11:30:00Z"},
        {"id": "rate-alpha-4", "provider": "Dr. Alpha 4", "start": "2030-12-21T12:00:00Z", "end": "2030-12-21T12:30:00Z"},
        {"id": "rate-alpha-5", "provider": "Dr. Alpha 5", "start": "2030-12-21T13:00:00Z", "end": "2030-12-21T13:30:00Z"},
        {"id": "rate-beta-1", "provider": "Dr. Beta 1", "start": "2030-12-21T14:00:00Z", "end": "2030-12-21T14:30:00Z"},
    ]
    client.post("/reset", json={"slots": slots}, headers=headers)

    for index in range(RATE_LIMIT_MAX_ATTEMPTS):
        response = client.post(
            "/bookings",
            json={"slot_id": f"rate-alpha-{index + 1}", "name": "Alpha", "email": "alpha@example.com"},
            headers=headers,
        )
        assert response.status_code == 201, response.json()

    response = client.post(
        "/bookings",
        json={"slot_id": "rate-beta-1", "name": "Beta", "email": "beta@example.com"},
        headers=headers,
    )
    assert response.status_code == 201


def test_failed_booking_attempts_count_with_normalized_email(client):
    headers = {"X-API-Key": "test-api-key"}
    response = client.post(
        "/reset",
        json={
            "slots": [
                {
                    "id": "rate-after-failures",
                    "provider": "Dr. Recovery",
                    "start": "2030-12-22T09:00:00Z",
                    "end": "2030-12-22T09:30:00Z",
                }
            ]
        },
        headers=headers,
    )
    assert response.status_code == 200

    for _ in range(RATE_LIMIT_MAX_ATTEMPTS):
        failed = client.post(
            "/bookings",
            json={
                "slot_id": "missing-slot",
                "name": "Failed Patient",
                "email": "Failed.User@Example.com",
            },
            headers=headers,
        )
        assert failed.status_code == 404

    blocked = client.post(
        "/bookings",
        json={
            "slot_id": "rate-after-failures",
            "name": "Failed Patient",
            "email": "failed.user@example.com",
        },
        headers=headers,
    )
    assert blocked.status_code == 429
    assert re.fullmatch(r"[0-9]+", blocked.headers["Retry-After"])


def test_expired_attempts_no_longer_count_towards_limit():
    session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        session.add_all(
            [
                BookingAttempt(email="aging@example.com", attempted_at=now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS + 10)),
                BookingAttempt(email="aging@example.com", attempted_at=now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS + 20)),
            ]
        )
        session.commit()

        allowed, retry_after = can_attempt_booking(session, "aging@example.com")
        assert allowed is True
        assert retry_after == 0
    finally:
        session.close()


def test_concurrent_requests_cannot_bypass_limit(client):
    headers = {"X-API-Key": "test-api-key"}
    slots = [
        {"id": f"rate-concurrent-{index}", "provider": f"Dr. Concurrency {index}", "start": f"2030-12-{index:02d}T09:00:00Z", "end": f"2030-12-{index:02d}T09:30:00Z"}
        for index in range(1, 12)
    ]
    response = client.post("/reset", json={"slots": slots}, headers=headers)
    assert response.status_code == 200

    email = "Concurrent.User@Example.com"

    def attempt(slot_id: str):
        request_client = TestClient(app)
        return request_client.post(
            "/bookings",
            json={"slot_id": slot_id, "name": "Concurrent User", "email": email},
            headers=headers,
        )

    with ThreadPoolExecutor(max_workers=10) as pool:
        results = list(pool.map(attempt, [f"rate-concurrent-{i}" for i in range(1, 11)]))

    statuses = [result.status_code for result in results]
    assert statuses.count(201) == RATE_LIMIT_MAX_ATTEMPTS
    assert statuses.count(429) == 10 - RATE_LIMIT_MAX_ATTEMPTS
    for result in results:
        if result.status_code == 429:
            retry_after = result.headers.get("Retry-After", "")
            assert re.fullmatch(r"[0-9]+", retry_after)
            assert int(retry_after) > 0

    independent = client.post(
        "/bookings",
        json={
            "slot_id": "rate-concurrent-11",
            "name": "Independent User",
            "email": "other.user@example.com",
        },
        headers=headers,
    )
    assert independent.status_code == 201
