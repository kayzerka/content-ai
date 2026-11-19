"""Meta webhook receiver: fail closed until durable storage is configured."""

import hashlib
import hmac
import json
import logging
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
        instagram_secret = os.environ.get(
            "META_DIAG_INSTAGRAM_APP_SECRET"
        )
        if instagram_secret:
            instagram_expected = hmac.new(
                instagram_secret.encode(),
                raw,
                hashlib.sha256
            ).hexdigest()
            instagram_match = hmac.compare_digest(
                received,
                instagram_expected
            )
            logging.getLogger(__name__).warning(
                "META_INSTAGRAM_HMAC_DIAGNOSTIC match=%s",
                instagram_match,
            )
        else:
            logging.getLogger(__name__).warning(
                "META_INSTAGRAM_HMAC_DIAGNOSTIC NOT_CONFIGURED"
            )

        try:
            diagnostic_payload = json.loads(raw)
            if isinstance(diagnostic_payload, dict):
                entries = diagnostic_payload.get("entry", [])
                if not isinstance(entries, list):
                    entries = []

                fields = set()
                messaging_count = 0

                for entry in entries[:100]:
                    if not isinstance(entry, dict):
                        continue

                    changes = entry.get("changes", [])
                    if isinstance(changes, list):
                        for change in changes[:100]:
                            if isinstance(change, dict):
                                field = change.get("field")
                                if isinstance(field, str):
                                    if field in (
                                        "messages",
                                        "messaging_postbacks",
                                        "comments",
                                        "live_comments",
                                        "mentions",
                                    ):
                                        fields.add(field)
                                    else:
                                        fields.add("other")

                    messaging = entry.get("messaging", [])
                    if isinstance(messaging, list):
                        messaging_count += len(messaging)

                logging.getLogger(__name__).warning(
                    "META_EVENT_DIAGNOSTIC "
                    "object=%s entry_count=%s fields=%s "
                    "messaging_count=%s",
                    diagnostic_payload.get("object")
                    if diagnostic_payload.get("object") in
                    ("instagram", "page") else "other",
                    len(entries),
                    ",".join(sorted(fields)) or "none",
                    messaging_count,
                )
        except (ValueError, UnicodeDecodeError, TypeError):
            logging.getLogger(__name__).warning(
                "META_EVENT_DIAGNOSTIC invalid_json"
            )
        diagnostic_results = {}
        for label, env_name in (
            ("posting", "META_DIAG_POSTING_APP_SECRET"),
            ("automation", "META_DIAG_AUTOMATION_APP_SECRET"),
        ):
            candidate = os.getenv(env_name, "").strip()
            if candidate:
                candidate_signature = (
                    "sha256="
                    + hmac.new(
                        candidate.encode("utf-8"),
                        raw,
                        hashlib.sha256,
                    ).hexdigest()
                )
                diagnostic_results[label] = hmac.compare_digest(
                    received, candidate_signature
                )
            else:
                diagnostic_results[label] = "NOT_CONFIGURED"

        try:
            parsed = json.loads(raw)
            compact = json.dumps(
                parsed,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode("utf-8")
            normalized = json.dumps(
                parsed,
                ensure_ascii=False,
            ).encode("utf-8")
            variants = {
                "compact": compact,
                "normalized": normalized,
            }
            variant_matches = {}
            for variant_name, variant_body in variants.items():
                matches = []
                for app_name, secret_name in (
                    ("primary", "META_APP_SECRET"),
                    ("posting", "META_DIAG_POSTING_APP_SECRET"),
                    ("automation", "META_DIAG_AUTOMATION_APP_SECRET"),
                ):
                    secret = os.getenv(secret_name, "").strip()
                    if secret:
                        candidate = "sha256=" + hmac.new(
                            secret.encode("utf-8"),
                            variant_body,
                            hashlib.sha256,
                        ).hexdigest()
                        if hmac.compare_digest(received, candidate):
                            matches.append(app_name)
                variant_matches[variant_name] = matches
            logging.getLogger(__name__).warning(
                "META_BODY_DIAGNOSTIC compact=%s normalized=%s",
                variant_matches["compact"],
                variant_matches["normalized"],
            )
        except (ValueError, UnicodeDecodeError, TypeError):
            logging.getLogger(__name__).warning(
                "META_BODY_DIAGNOSTIC invalid_json"
            )

        logging.getLogger(__name__).warning(
            "META_HMAC_DIAGNOSTIC posting=%s automation=%s",
            diagnostic_results["posting"],
            diagnostic_results["automation"],
        )
        logging.getLogger(__name__).warning(
            "META_SIGNATURE_REJECTED "
            "header_present=%s format_valid=%s "
            "body_bytes=%s body_sha256_prefix=%s",
            bool(received),
            received.startswith("sha256=") and len(received) == 71,
            len(raw),
            hashlib.sha256(raw).hexdigest()[:12],
        )
        raise HTTPException(403, "Invalid Meta webhook signature")


@router.post("/meta/webhook/v2")
async def receive_meta_webhook(request: Request):
    raw = await request.body()

    if request.headers.get("X-Hub-Signature"):
        logging.getLogger(__name__).info(
            "META_LEGACY_SIGNATURE_HEADER_PRESENT"
        )

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
        logging.getLogger(__name__).exception(
            "Meta durable queue write failed"
        )
        raise HTTPException(
            status_code=503,
            detail="Durable webhook storage unavailable",
        )

    return {"ok": True, "queued": inserted}
