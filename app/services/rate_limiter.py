from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models import BookingAttempt


RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_ATTEMPTS = 5


def can_attempt_booking(db: Session, email: str) -> tuple[bool, int]:
    normalized = email.strip().lower()
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)
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
        if oldest is None:
            retry_after = RATE_LIMIT_WINDOW_SECONDS
        else:
            retry_after = max(1, int((oldest + timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS) - datetime.now(timezone.utc).replace(tzinfo=None)).total_seconds()))
        return False, retry_after
    return True, 0


def record_booking_attempt(db: Session, email: str) -> None:
    normalized = email.strip().lower()
    attempt = BookingAttempt(email=normalized, attempted_at=datetime.now(timezone.utc).replace(tzinfo=None))
    db.add(attempt)
    db.flush()
