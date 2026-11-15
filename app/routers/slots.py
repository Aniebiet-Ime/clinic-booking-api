from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_api_key
from app.schemas import ResetRequest, SlotResponse
from app.services.booking_service import get_available_slots, reset_slots

router = APIRouter(tags=["slots"])


@router.get("/slots")
def list_slots(
    provider: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_api_key),
):
    return {"slots": [
        {
            "id": item["id"],
            "provider": item["provider"],
            "start": item["start"].isoformat().replace("+00:00", "Z") if hasattr(item["start"], "isoformat") else item["start"],
            "end": item["end"].isoformat().replace("+00:00", "Z") if hasattr(item["end"], "isoformat") else item["end"],
            "available": item["available"],
        }
        for item in get_available_slots(db, provider=provider)
    ]}


@router.post("/reset")
def reset(
    payload: ResetRequest,
    db: Session = Depends(get_db),
    _api_key: str = Depends(require_api_key),
):
    reset_slots(db, [slot.model_dump(mode="json") for slot in payload.slots])
    return {"status": "ok"}
