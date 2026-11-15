import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import IdempotencyRecord


def request_fingerprint(payload: Any) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def acquire_idempotency_lock(db: Session, key: str) -> None:
    if not key:
        return
    if getattr(db.bind, "dialect", None) is not None and db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": key})


def get_idempotency_record(db: Session, key: str):
    if not key:
        return None
    return db.execute(
        select(IdempotencyRecord)
        .where(IdempotencyRecord.idempotency_key == key)
        .with_for_update()
    ).scalar_one_or_none()


def delete_incomplete_idempotency_record(db: Session, key: str) -> None:
    if not key:
        return
    record = get_idempotency_record(db, key)
    if record is not None and record.response_status in (None, 0) and not record.response_body:
        db.delete(record)
        db.flush()
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise


def store_idempotency_response(db: Session, record: IdempotencyRecord, response_body: dict, status_code: int) -> None:
    record.response_body = json.dumps(response_body, separators=(",", ":"), ensure_ascii=True)
    record.response_status = status_code
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    db.flush()
