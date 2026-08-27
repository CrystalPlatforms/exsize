from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from exsize.database import get_db
from exsize.deps import get_current_user
from exsize.models import User

router = APIRouter(prefix="/api", tags=["settings"])


class SettingsResponse(BaseModel):
    language: str
    phone_number: str | None = None
    model_config = {"from_attributes": True}


class UpdateSettingsRequest(BaseModel):
    language: Literal["en", "pl"]
    # PII — stored on the user, never hardcoded or logged. Only updated when the
    # key is present in the request; null inside a present key clears the value.
    phone_number: str | None = None


@router.get("/settings", response_model=SettingsResponse)
def get_settings(user: User = Depends(get_current_user)):
    return SettingsResponse(language=user.language, phone_number=user.phone_number)


@router.patch("/settings", response_model=SettingsResponse)
def update_settings(
    body: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user.language = body.language
    if "phone_number" in body.model_fields_set:
        phone = (body.phone_number or "").strip()
        user.phone_number = phone or None
    db.add(user)
    db.commit()
    db.refresh(user)
    return SettingsResponse(language=user.language, phone_number=user.phone_number)
