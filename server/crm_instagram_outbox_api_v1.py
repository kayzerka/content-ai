"""Opt-in authenticated CRM Instagram outbox API. Never mount on public Meta gateway."""
import hmac
import os
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from crm_instagram_outbox_v1 import create_draft, list_drafts, approve_and_send, reject
from crm_outbox_telegram_bridge_v1 import notify_admin

router = APIRouter(prefix="/api/crm/instagram/outbox", tags=["crm-instagram-outbox"])

def require_admin(authorization: str = Header(default="")):
    secret = os.getenv("CRM_INSTAGRAM_OUTBOX_ADMIN_TOKEN", "").strip()
    if not secret or not hmac.compare_digest(authorization, "Bearer " + secret):
        raise HTTPException(401, "CRM outbox administrator token required")

class DraftInput(BaseModel):
    funnel_id: int = Field(gt=0)
    external_user_id: str = Field(pattern=r"^[0-9]+$", max_length=64)

@router.get("")
def get_outbox(_: None = Depends(require_admin)):
    return {"items": list_drafts()}

@router.post("")
def draft(body: DraftInput, _: None = Depends(require_admin)):
    try:
        return create_draft(body.funnel_id, body.external_user_id)
    except (ValueError, PermissionError) as exc:
        raise HTTPException(409, str(exc))

@router.post("/{draft_id}/notify")
def notify(draft_id: str, _: None = Depends(require_admin)):
    rows = [r for r in list_drafts() if r["id"] == draft_id]
    if not rows or rows[0]["status"] != "pending_approval":
        raise HTTPException(409, "draft not pending")
    try:
        return notify_admin(rows[0])
    except (ValueError, PermissionError) as exc:
        raise HTTPException(409, str(exc))

@router.post("/{draft_id}/approve-send")
def approve_send(draft_id: str, _: None = Depends(require_admin)):
    try:
        return approve_and_send(draft_id, "crm_admin")
    except (ValueError, PermissionError) as exc:
        raise HTTPException(409, str(exc))

@router.post("/{draft_id}/reject")
def decline(draft_id: str, _: None = Depends(require_admin)):
    try:
        return reject(draft_id, "crm_admin")
    except (ValueError, PermissionError) as exc:
        raise HTTPException(409, str(exc))
