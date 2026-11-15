from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from app.models import BookingAttempt


RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 5


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _to_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _acquire_email_lock(db: Session, email: str) -> None:
    if getattr(db.bind, "dialect", None) is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:email))"), {"email": email})


def can_attempt_booking(db: Session, email: str) -> tuple[bool, int]:
    normalized = _normalize_email(email)
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
    _acquire_email_lock(db, normalized)

    count = db.scalar(
        select(func.count()).select_from(BookingAttempt).where(
            and_(BookingAttempt.email == normalized, BookingAttempt.attempted_at >= cutoff)
        )
    ) or 0
    if count >= RATE_LIMIT_MAX_ATTEMPTS:
        oldest = db.execute(
            select(BookingAttempt.attempted_at)
            .where(and_(BookingAttempt.email == normalized, BookingAttempt.attempted_at >= cutoff))
            .order_by(BookingAttempt.attempted_at.asc())
            .limit(1)
        ).scalar()
        oldest_utc = _to_utc(oldest)
        if oldest_utc is None:
            retry_after = RATE_LIMIT_WINDOW_SECONDS
        else:
            retry_after = max(1, int((oldest_utc + timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS) - now).total_seconds()))
        return False, retry_after
    return True, 0


def record_booking_attempt(db: Session, email: str) -> None:
    normalized = _normalize_email(email)
    attempt = BookingAttempt(email=normalized, attempted_at=datetime.now(timezone.utc))
    db.add(attempt)
    db.flush()
