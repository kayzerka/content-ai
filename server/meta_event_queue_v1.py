"""Durable PostgreSQL inbox for signed Meta webhook payloads."""

import hashlib
import json
import os
import uuid


SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS meta_private;
CREATE TABLE IF NOT EXISTS meta_private.meta_webhook_events (
    id BIGSERIAL PRIMARY KEY,
    event_key TEXT NOT NULL UNIQUE,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    lease_id UUID,
    leased_until TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS meta_webhook_events_pending_idx
ON meta_private.meta_webhook_events (received_at, id)
WHERE processed_at IS NULL;
"""


def connect():
    import psycopg

    url = os.environ.get("META_QUEUE_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("META_QUEUE_DATABASE_URL not configured")

    return psycopg.connect(url, connect_timeout=10)


def initialize():
    with connect() as db:
        db.execute(SCHEMA_SQL)


def enqueue(raw: bytes, payload: dict) -> bool:
    from psycopg.types.json import Jsonb

    event_key = hashlib.sha256(raw).hexdigest()

    with connect() as db:
        result = db.execute(
            """
            INSERT INTO meta_private.meta_webhook_events (event_key, payload)
            VALUES (%s, %s)
            ON CONFLICT (event_key) DO NOTHING
            RETURNING id
            """,
            (event_key, Jsonb(payload)),
        ).fetchone()

        return result is not None


def claim_batch(limit: int = 50, lease_seconds: int = 300):
    limit = max(1, min(int(limit), 100))
    lease_seconds = max(30, min(int(lease_seconds), 3600))
    lease_id = uuid.uuid4()

    with connect() as db:
        rows = db.execute(
            """
            WITH claimed AS (
                SELECT id
                FROM meta_private.meta_webhook_events
                WHERE processed_at IS NULL
                  AND (leased_until IS NULL OR leased_until < NOW())
                ORDER BY id
                LIMIT %s
                FOR UPDATE SKIP LOCKED
            )
            UPDATE meta_private.meta_webhook_events AS e
            SET lease_id = %s,
                leased_until = NOW() + (%s * INTERVAL '1 second'),
                attempts = attempts + 1
            FROM claimed
            WHERE e.id = claimed.id
            RETURNING e.id, e.payload
            """,
            (limit, lease_id, lease_seconds),
        ).fetchall()

    return {
        "lease_id": str(lease_id),
        "events": [
            {"id": row[0], "payload": row[1]}
            for row in rows
        ],
    }


def acknowledge(event_id: int, lease_id: str) -> bool:
    with connect() as db:
        row = db.execute(
            """
            UPDATE meta_private.meta_webhook_events
            SET processed_at = NOW(),
                lease_id = NULL,
                leased_until = NULL
            WHERE id = %s
              AND lease_id = %s
              AND processed_at IS NULL
              AND leased_until > NOW()
            RETURNING id
            """,
            (event_id, uuid.UUID(lease_id)),
        ).fetchone()

        return row is not None


def history_batch(after_id: int = 0, limit: int = 100):
    """Read-only pagination including acknowledged webhook events."""
    after_id = max(0, int(after_id))
    limit = max(1, min(int(limit), 100))

    with connect() as db:
        rows = db.execute(
            """SELECT id, payload
               FROM meta_private.meta_webhook_events
               WHERE id > %s
               ORDER BY id ASC
               LIMIT %s""",
            (after_id, limit),
        ).fetchall()

    return {
        "events": [
            {"id": row[0], "payload": row[1]}
            for row in rows
        ],
        "next_after_id": rows[-1][0] if rows else after_id,
        "has_more": len(rows) == limit,
    }
