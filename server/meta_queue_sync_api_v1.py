"""Authenticated API for Mac CRM synchronization."""

import hmac
import os
import uuid

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from meta_event_queue_v1 import acknowledge, claim_batch

router = APIRouter(prefix="/api/meta-queue")


def authorize(authorization: str | None):
    expected = os.getenv("META_QUEUE_SYNC_TOKEN", "").strip()

    if not expected:
        raise HTTPException(503, "Queue sync not configured")

    if not authorization or not hmac.compare_digest(
        authorization,
        "Bearer " + expected,
    ):
        raise HTTPException(401, "Unauthorized")


class AckRequest(BaseModel):
    event_id: int = Field(gt=0)
    lease_id: uuid.UUID


@router.post("/claim")
def claim(
    authorization: str | None = Header(default=None),
):
    authorize(authorization)

    try:
        return claim_batch(limit=25, lease_seconds=600)
    except Exception:
        raise HTTPException(503, "Queue unavailable")


@router.post("/ack")
def ack(
    request: AckRequest,
    authorization: str | None = Header(default=None),
):
    authorize(authorization)

    try:
        acknowledged = acknowledge(
            request.event_id,
            str(request.lease_id),
        )
    except Exception:
        raise HTTPException(503, "Queue unavailable")

    if not acknowledged:
        raise HTTPException(409, "Lease expired or event already processed")

    return {"ok": True, "acknowledged": True}
