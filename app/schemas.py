from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SlotPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    provider: str
    start: datetime
    end: datetime

    @field_validator("id", "provider")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("start", "end")
    @classmethod
    def validate_times(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return value


class ResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slots: list[SlotPayload] = Field(default_factory=list)


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    name: str
    email: EmailStr

    @field_validator("slot_id", "name")
    @classmethod
    def strip_and_check(cls, value: str) -> str:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("must not be empty")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class BookingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slot_id: str
    name: str
    email: str
    status: str
    created_at: datetime


class BookingHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    slot_id: str
    name: str
    email: str
    status: str
    created_at: datetime


class BookingHistoryResponse(BaseModel):
    bookings: list[BookingHistoryEntry]
    next_cursor: str | None = None


class SlotResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    start: datetime
    end: datetime
    available: bool
