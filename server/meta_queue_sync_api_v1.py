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


@router.get("/history")
def history(
    after_id: int = 0,
    limit: int = 100,
    authorization: str | None = Header(default=None),
):
    """Authenticated read-only Meta event history."""
    authorize(authorization)

    if after_id < 0 or not 1 <= limit <= 100:
        raise HTTPException(422, "Invalid pagination")

    try:
        from meta_event_queue_v1 import history_batch
        return history_batch(after_id=after_id, limit=limit)
    except Exception:
        raise HTTPException(503, "Queue history unavailable")


@router.get("/instagram-history-check")
def instagram_history_check(
    authorization: str | None = Header(default=None),
):
    """Read-only Instagram Graph API access check on Render."""
    authorize(authorization)

    import requests

    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("FB_PAGE_ID", "").strip()
    ig_id = os.getenv("IG_USER_ID", "").strip()

    configured = {
        "FB_PAGE_ACCESS_TOKEN": bool(token),
        "FB_PAGE_ID": bool(page_id),
        "IG_USER_ID": bool(ig_id),
    }

    if not all(configured.values()):
        return {
            "ok": False,
            "reason": "MISSING_CONFIGURATION",
            "configured": configured,
        }

    try:
        response = requests.get(
            f"https://graph.facebook.com/v25.0/{page_id}/conversations",
            params={
                "platform": "instagram",
                "fields": "id,updated_time",
                "limit": 5,
                "access_token": token,
            },
            timeout=20,
        )
        result = response.json()

        if not response.ok or "error" in result:
            error = result.get("error") or {}
            return {
                "ok": False,
                "reason": "META_API_ERROR",
                "code": error.get("code"),
                "subcode": error.get("error_subcode"),
                "error_type": error.get("type"),
            }

        return {
            "ok": True,
            "conversations_in_first_page": len(result.get("data", [])),
            "has_more": bool(
                (result.get("paging") or {}).get("next")
            ),
            "crm_writes": False,
            "outbound_messages": False,
        }

    except Exception as exc:
        return {
            "ok": False,
            "reason": "META_REQUEST_FAILED",
            "error_type": type(exc).__name__,
        }

@router.get("/instagram-history-page")
def instagram_history_page(
    kind: str = "conversations",
    conversation_id: str = "",
    after: str = "",
    authorization: str | None = Header(default=None),
):
    """Authenticated, read-only Instagram Direct pagination."""
    authorize(authorization)

    import re
    import requests

    token = os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
    page_id = os.getenv("FB_PAGE_ID", "").strip()

    if not token or not page_id:
        raise HTTPException(503, "Meta credentials unavailable")

    if kind == "conversations":
        path = page_id + "/conversations"
        params = {
            "platform": "instagram",
            "fields": "id,updated_time,participants",
            "limit": 25,
        }
    elif kind == "messages":
        if not re.fullmatch(r"[A-Za-z0-9_]+", conversation_id):
            raise HTTPException(422, "Invalid conversation ID")
        path = conversation_id + "/messages"
        params = {
            "fields": "id,message,from,to,created_time",
            "limit": 25,
        }
    else:
        raise HTTPException(422, "Invalid kind")

    if after:
        if len(after) > 2048 or any(c.isspace() for c in after):
            raise HTTPException(422, "Invalid cursor")
        params["after"] = after

    try:
        response = requests.get(
            "https://graph.facebook.com/v25.0/" + path,
            params={**params, "access_token": token},
            timeout=30,
        )
        result = response.json()
    except (requests.RequestException, ValueError):
        raise HTTPException(502, "Meta request failed")

    if not response.ok or "error" in result:
        error = result.get("error") or {}
        return {
            "ok": False,
            "code": error.get("code"),
            "subcode": error.get("error_subcode"),
        }

    paging = result.get("paging") or {}
    cursors = paging.get("cursors") or {}

    return {
        "ok": True,
        "data": result.get("data") or [],
        "has_more": bool(paging.get("next")),
        "next_after": cursors.get("after") or "",
    }
