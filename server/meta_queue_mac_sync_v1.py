"""Pull durable Meta events from Render into local CRM."""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

from crm_instagram_ingest import ingest_instagram_event


def api_call(endpoint, payload):
    base = os.environ["META_QUEUE_BASE_URL"].rstrip("/")
    token = os.environ["META_QUEUE_SYNC_TOKEN"]

    request = urllib.request.Request(
        base + "/api/meta-queue/" + endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def extract_events(payload):
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value") or {}
            sender = value.get("from") or {}

            event_id = (
                value.get("comment_id")
                or value.get("id")
                or value.get("mid")
            )

            if not event_id:
                event_id = hashlib.sha256(
                    json.dumps(
                        {"entry_id": entry.get("id"), "change": change},
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest()

            yield {
                "external_user_id": str(
                    sender.get("id")
                    or value.get("sender_id")
                    or value.get("user_id")
                    or ""
                ),
                "external_event_id": str(event_id),
                "event_type": str(change.get("field") or "change"),
                "text": str(
                    value.get("text")
                    or value.get("message")
                    or value.get("comment")
                    or ""
                ),
                "username": str(
                    sender.get("username")
                    or value.get("username")
                    or ""
                ),
                "is_echo": False,
            }

        for message_event in entry.get("messaging", []) or []:
            message = message_event.get("message") or {}

            event_id = message.get("mid")
            if not event_id:
                event_id = hashlib.sha256(
                    json.dumps(
                        message_event,
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest()

            yield {
                "external_user_id": str(
                    (message_event.get("sender") or {}).get("id") or ""
                ),
                "external_event_id": str(event_id),
                "event_type": "message",
                "text": str(message.get("text") or ""),
                "username": "",
                "is_echo": bool(
                    message_event.get("is_echo")
                    or message.get("is_echo")
                ),
            }


def sync_once():
    batch = api_call("claim", {})
    lease_id = batch["lease_id"]

    for item in batch["events"]:
        event_id = item["id"]
        payload = item["payload"]

        try:
            for event in extract_events(payload):
                if event.pop("is_echo"):
                    continue

                result = ingest_instagram_event(**event)

                if result["status"] not in (
                    "created",
                    "updated",
                    "duplicate",
                    "skipped",
                ):
                    raise RuntimeError(
                        "Unexpected CRM result: " + repr(result)
                    )

            api_call("ack", {
                "event_id": event_id,
                "lease_id": lease_id,
            })

            print("ACK:", event_id, flush=True)

        except Exception as exc:
            print(
                "SYNC FAILED:",
                event_id,
                type(exc).__name__,
                str(exc)[:200],
                file=sys.stderr,
                flush=True,
            )
            # No ACK: event becomes available after lease expiry.

    return len(batch["events"])


if __name__ == "__main__":
    print("CLAIMED:", sync_once())
