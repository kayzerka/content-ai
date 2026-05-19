from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from services.safety_calendar.generator import generate_safety_calendar

router = APIRouter(prefix="/api/safety-calendar", tags=["safety-calendar"])


class SafetyCalendarRequest(BaseModel):
    birth_date: str = Field(..., example="1990-05-12")
    birth_time: Optional[str] = Field(None, example="14:30")
    birth_place: Optional[str] = Field(None, example="Kyiv, Ukraine")
    current_location: Optional[str] = Field(None, example="Wesel, Germany")
    start_date: Optional[str] = Field(None, example="2026-05-19")
    period_days: int = Field(7, ge=1, le=30)


@router.post("/generate")
def generate_calendar(payload: SafetyCalendarRequest):
    return generate_safety_calendar(payload.model_dump())
