"""Meta webhook receiver: fail closed until durable storage is configured."""

import hashlib
import hmac
import json
import os

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


def verify_signature(raw: bytes, received: str) -> None:
    secret = os.getenv("META_APP_SECRET", "").strip()
    if not secret:
        raise HTTPException(503, "Meta signature verification unavailable")

    expected = "sha256=" + hmac.new(
        secret.encode("utf-8"), raw, hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(received, expected):
        logging.getLogger(__name__).warning(
            "META_SIGNATURE_REJECTED header_present=%s format_valid=%s",
            bool(received),
            received.startswith("sha256=") and len(received) == 71,
        )
        raise HTTPException(403, "Invalid Meta webhook signature")


@router.post("/meta/webhook/v2")
async def receive_meta_webhook(request: Request):
    raw = await request.body()

    verify_signature(
        raw,
        request.headers.get("X-Hub-Signature-256", ""),
    )

    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, "Invalid JSON")

    if not isinstance(payload, dict):
        raise HTTPException(400, "Expected JSON object")

    # Persist before acknowledging Meta. Duplicate deliveries are successful.
    # No SQLite, CRM, funnel or outbound messaging side effects.
    try:
        from meta_event_queue_v1 import enqueue
        inserted = enqueue(raw, payload)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Meta durable queue write failed"
        )
        raise HTTPException(
            status_code=503,
            detail="Durable webhook storage unavailable",
        )

    return {"ok": True, "queued": inserted}
