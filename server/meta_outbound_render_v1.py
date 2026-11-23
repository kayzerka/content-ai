"""Render-side, explicitly approved single-recipient Instagram DM relay."""
import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/meta-outbound")

class SendRequest(BaseModel):
    recipient_id: str = Field(min_length=1, max_length=64, pattern=r"^[0-9]+$")
    text: str = Field(min_length=1, max_length=1000)
    request_id: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    confirmed: bool

def _authorize(authorization):
    expected = os.getenv("META_OUTBOUND_TOKEN", "").strip()
    if not expected:
        raise HTTPException(503, "Outbound authentication not configured")
    if not authorization or not hmac.compare_digest(authorization, "Bearer " + expected):
        raise HTTPException(401, "Unauthorized")

@router.post("/send-once")
def send_once(body: SendRequest, authorization: str | None = Header(default=None)):
    _authorize(authorization)
    if os.getenv("META_OUTBOUND_ENABLED", "0") != "1":
        raise HTTPException(503, "Outbound disabled")
    if body.confirmed is not True:
        raise HTTPException(400, "Explicit confirmation required")
    allowed = {s.strip() for s in os.getenv("META_OUTBOUND_ALLOWED_RECIPIENTS", "").split(",") if s.strip()}
    if body.recipient_id not in allowed:
        raise HTTPException(403, "Recipient not allowlisted")
    token = (os.getenv("FB_PAGE_ACCESS_TOKEN") or os.getenv("META_PAGE_ACCESS_TOKEN") or os.getenv("PAGE_ACCESS_TOKEN") or "").strip()
    page = (os.getenv("FB_PAGE_ID") or os.getenv("META_PAGE_ID") or os.getenv("PAGE_ID") or "").strip()
    if not token or not page:
        raise HTTPException(503, "Page credentials missing on Render")
    import psycopg
    db_url = os.getenv("META_QUEUE_DATABASE_URL", "").strip()
    if not db_url:
        raise HTTPException(503, "Durable database unavailable")
    fingerprint = hashlib.sha256(json.dumps([body.recipient_id, body.text], ensure_ascii=False).encode()).hexdigest()
    with psycopg.connect(db_url, connect_timeout=10) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS meta_private.meta_outbound_requests (
            request_id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, state TEXT NOT NULL,
            result JSONB, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )""")
        row = db.execute(
            """INSERT INTO meta_private.meta_outbound_requests(request_id,fingerprint,state)
               VALUES (%s,%s,'pending') ON CONFLICT DO NOTHING RETURNING request_id""",
            (body.request_id, fingerprint)
        ).fetchone()
        if row is None:
            previous = db.execute("SELECT fingerprint,state,result FROM meta_private.meta_outbound_requests WHERE request_id=%s", (body.request_id,)).fetchone()
            if previous and previous[0] != fingerprint:
                raise HTTPException(409, "Request ID reused with different message")
            return {"ok": False, "status": previous[1] if previous else "unknown", "duplicate": True,
                    "result": previous[2] if previous else None}
    # A pending request is never retried automatically: uncertain network outcomes are handled manually.
    version = os.getenv("META_GRAPH_VERSION", "v20.0").strip()
    url = f"https://graph.facebook.com/{version}/{page}/messages"
    payload = json.dumps({"messaging_type":"RESPONSE","recipient":{"id":body.recipient_id},"message":{"text":body.text}}).encode()
    req = urllib.request.Request(url, data=payload, method="POST",
        headers={"Content-Type":"application/json", "Authorization":"Bearer "+token})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode())
        state = "accepted"
        safe_result = {"message_id": result.get("message_id"), "recipient_id": result.get("recipient_id")}
    except urllib.error.HTTPError as exc:
        state = "rejected"
        try:
            error = json.loads(exc.read().decode()).get("error", {})
        except (ValueError, UnicodeDecodeError):
            error = {}
        safe_result = {"http_status": exc.code, "code": error.get("code"),
                       "subcode": error.get("error_subcode"), "message": str(error.get("message",""))[:250]}
    except Exception:
        state = "unknown"
        safe_result = {"error":"Network outcome uncertain; do not retry automatically"}
    from psycopg.types.json import Jsonb
    with psycopg.connect(db_url, connect_timeout=10) as db:
        db.execute("UPDATE meta_private.meta_outbound_requests SET state=%s,result=%s WHERE request_id=%s",
                   (state, Jsonb(safe_result), body.request_id))
    return {"ok":state=="accepted", "status":state, "result":safe_result, "duplicate":False}
