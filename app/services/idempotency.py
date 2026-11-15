import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IdempotencyRecord


def request_fingerprint(payload: Any) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def get_idempotency_record(db: Session, key: str):
    if not key:
        return None
    return db.execute(
        select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
    ).scalar_one_or_none()


def store_idempotency_response(db: Session, record: IdempotencyRecord, response_body: dict, status_code: int) -> None:
    record.response_body = json.dumps(response_body, separators=(",", ":"), ensure_ascii=True)
    record.response_status = status_code
    record.updated_at = datetime.now(timezone.utc)
    db.add(record)
    db.flush()
