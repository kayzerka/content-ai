"""Local-only, manually confirmed Instagram Direct UI proxy.

No automatic sends. No credentials persisted or exposed to the browser by the server.
"""
import hmac
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter()
BASE_DIR = Path(__file__).resolve().parent
RENDER_ENDPOINT = "https://content-ai-ps1k.onrender.com/api/meta-outbound/send-once"
TEST_RECIPIENT = "3100596540128323"

class ManualDM(BaseModel):
    recipient_id: str = Field(pattern=r"^[0-9]+$", min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=1000)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_-]+$", min_length=8, max_length=100)
    confirmed: bool
    token: str = Field(default="", max_length=4096)

def _local_only(request: Request):
    client = request.client.host if request.client else ""
    if client not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "Local access only")
    origin = request.headers.get("origin")
    if origin:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise HTTPException(403, "Origin not allowed")

@router.get("/instagram-direct")
def instagram_direct_page(request: Request):
    _local_only(request)
    return FileResponse(BASE_DIR / "static" / "instagram-direct.html",
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
                                 "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; form-action 'none'"})

@router.post("/api/crm/instagram/direct/send-once")
def instagram_direct_send_once(body: ManualDM, request: Request):
    _local_only(request)
    if not body.confirmed:
        raise HTTPException(400, "Manual confirmation required")
    if body.recipient_id != TEST_RECIPIENT:
        raise HTTPException(403, "Only previously verified recipient is enabled")
    token = (os.getenv("META_OUTBOUND_TOKEN") or body.token).strip()
    if not token:
        raise HTTPException(503, "META_OUTBOUND_TOKEN required (enter it in the form)")
    data = json.dumps({"recipient_id": body.recipient_id, "text": body.text,
                       "request_id": body.request_id, "confirmed": True},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(RENDER_ENDPOINT, data=data, method="POST",
          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result
    except urllib.error.HTTPError as exc:
        try:
            detail = json.loads(exc.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            detail = {"detail": "Render returned HTTP error"}
        raise HTTPException(exc.code, detail)
    except Exception:
        raise HTTPException(502, "Network outcome uncertain. Check Render logs before retrying.")
