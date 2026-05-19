from __future__ import annotations

import json
import base64
import requests
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




def _github_put_file(path: str, content_text: str, message: str):
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GITHUB_BACKUP_TOKEN")
    repo = os.getenv("GITHUB_REPO") or os.getenv("GITHUB_BACKUP_REPO") or "kayzerka/content-ai"
    branch = os.getenv("GITHUB_BRANCH") or os.getenv("GITHUB_BACKUP_BRANCH") or "main"

    if not token:
        return {"ok": False, "error": "GITHUB_TOKEN missing"}

    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }

    sha = None
    get_r = requests.get(api_url, headers=headers, params={"ref": branch}, timeout=20)
    if get_r.status_code == 200:
        sha = get_r.json().get("sha")

    payload = {
        "message": message,
        "content": base64.b64encode(content_text.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }

    if sha:
        payload["sha"] = sha

    put_r = requests.put(api_url, headers=headers, json=payload, timeout=30)

    return {
        "ok": put_r.status_code in (200, 201),
        "status_code": put_r.status_code,
        "response": put_r.text[:1000],
        "path": path,
    }


def export_users_payload():
    _init_db()

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

    return {
        "ok": True,
        "kind": "astranova_users_backup_v1",
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "count": len(rows),
        "users": [dict(r) for r in rows],
    }


def export_users_to_file_and_github(reason: str = "manual"):
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    data = export_users_payload()
    text = json.dumps(data, ensure_ascii=False, indent=2)

    BACKUP_FILE.write_text(text, encoding="utf-8")

    if int(data.get("count") or 0) <= 0 and reason not in ("allow_empty_manual",):
        return {
            "ok": False,
            "error": "blocked_empty_backup",
            "count": data.get("count", 0),
            "backup_file": str(BACKUP_FILE),
            "github": {
                "ok": False,
                "error": "empty backup was not pushed to GitHub"
            },
            "data": data,
        }

    github = _github_put_file(
        os.getenv("ASTRANOVA_BACKUP_PATH") or "server/backups/astranova-users-latest.json",
        text,
        f"backup AstraNova users: {reason}",
    )

    return {
        "ok": True,
        "count": data.get("count", 0),
        "backup_file": str(BACKUP_FILE),
        "github": github,
        "data": data,
    }


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
    return export_users_to_file_and_github("manual_export")



@router.get("/github/export")
def github_export():
    return export_users_to_file_and_github("manual_github_export")


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
