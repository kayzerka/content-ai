from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/astranova/backup", tags=["astranova-backup"])

DB_PATH = Path(os.getenv("CONTENT_DB_PATH") or "data/content.db")
BACKUP_DIR = Path("backups")
BACKUP_FILE = BACKUP_DIR / "astranova-users-latest.json"


def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(str(DB_PATH))


def _init_db():
    with _db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS astranova_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id TEXT UNIQUE,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            source_payload TEXT,

            birth_date TEXT,
            birth_time TEXT,
            birth_place TEXT,
            current_location TEXT,

            onboarding_state TEXT DEFAULT 'new',
            notifications_enabled INTEGER DEFAULT 1,

            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)
        con.commit()


@router.get("/counts")
def counts():
    _init_db()
    with _db() as con:
        total = con.execute("SELECT COUNT(*) FROM astranova_users").fetchone()[0]
        with_birth = con.execute(
            "SELECT COUNT(*) FROM astranova_users WHERE birth_date IS NOT NULL AND birth_date != ''"
        ).fetchone()[0]

    return {
        "ok": True,
        "db_path": str(DB_PATH),
        "total_users": total,
        "users_with_birth_date": with_birth,
        "backup_file": str(BACKUP_FILE),
        "backup_exists": BACKUP_FILE.exists(),
    }


@router.get("/export")
def export_users():
    _init_db()
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    with _db() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT
                telegram_user_id,
                username,
                first_name,
                last_name,
                source_payload,
                birth_date,
                birth_time,
                birth_place,
                current_location,
                onboarding_state,
                notifications_enabled,
                created_at,
                updated_at
            FROM astranova_users
            ORDER BY id ASC
        """).fetchall()

    data: Dict[str, Any] = {
        "ok": True,
        "kind": "astranova_users_backup_v1",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "count": len(rows),
        "users": [dict(r) for r in rows],
    }

    BACKUP_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    return {
        "ok": True,
        "count": len(rows),
        "backup_file": str(BACKUP_FILE),
        "data": data,
    }


@router.post("/restore")
def restore_users(payload: Dict[str, Any] = Body(...)):
    _init_db()

    users = payload.get("users")
    if not isinstance(users, list):
        return {
            "ok": False,
            "error": "payload must contain users list"
        }

    restored = 0

    with _db() as con:
        for u in users:
            telegram_user_id = str(u.get("telegram_user_id") or "").strip()
            if not telegram_user_id:
                continue

            con.execute("""
            INSERT INTO astranova_users (
                telegram_user_id,
                username,
                first_name,
                last_name,
                source_payload,
                birth_date,
                birth_time,
                birth_place,
                current_location,
                onboarding_state,
                notifications_enabled,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), COALESCE(?, CURRENT_TIMESTAMP))
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_name=excluded.last_name,
                source_payload=excluded.source_payload,
                birth_date=excluded.birth_date,
                birth_time=excluded.birth_time,
                birth_place=excluded.birth_place,
                current_location=excluded.current_location,
                onboarding_state=excluded.onboarding_state,
                notifications_enabled=excluded.notifications_enabled,
                updated_at=CURRENT_TIMESTAMP
            """, (
                telegram_user_id,
                u.get("username"),
                u.get("first_name"),
                u.get("last_name"),
                u.get("source_payload"),
                u.get("birth_date"),
                u.get("birth_time"),
                u.get("birth_place"),
                u.get("current_location"),
                u.get("onboarding_state") or "new",
                int(u.get("notifications_enabled", 1) or 0),
                u.get("created_at"),
                u.get("updated_at"),
            ))
            restored += 1

        con.commit()

    return {
        "ok": True,
        "restored": restored,
    }


@router.post("/restore-from-file")
def restore_from_file():
    if not BACKUP_FILE.exists():
        return {
            "ok": False,
            "error": "backup file not found",
            "backup_file": str(BACKUP_FILE),
        }

    payload = json.loads(BACKUP_FILE.read_text(encoding="utf-8"))
    return restore_users(payload)
