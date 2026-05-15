import os
import re
import json
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

router = APIRouter(prefix="/api/courses", tags=["courses"])

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backups" / "courses"
UPLOAD_DIR = BASE_DIR / "uploads" / "courses"
DB_PATH = DATA_DIR / "content.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-zA-Z0-9а-яА-ЯіїєґІЇЄҐ_-]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or f"course_{int(datetime.utcnow().timestamp())}"


def db() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), timeout=30)
    con.row_factory = sqlite3.Row
    ensure_schema(con)
    return con


def ensure_schema(con: sqlite3.Connection):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS course_projects (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_key TEXT UNIQUE NOT NULL,
      title TEXT NOT NULL,
      description TEXT,
      telegram_chat_id TEXT,
      telegram_channel_url TEXT,
      ai_system_prompt TEXT,
      status TEXT DEFAULT 'draft',
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS course_lessons (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_key TEXT NOT NULL,
      lesson_no INTEGER NOT NULL,
      title TEXT,
      topic TEXT,
      ai_prompt TEXT,
      lecture_text TEXT,
      telegram_post_text TEXT,
      status TEXT DEFAULT 'draft',
      published_at TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(course_key, lesson_no)
    );

    CREATE TABLE IF NOT EXISTS course_assets (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_key TEXT NOT NULL,
      lesson_no INTEGER NOT NULL,
      asset_type TEXT,
      file_name TEXT,
      file_path TEXT,
      mime_type TEXT,
      size_bytes INTEGER,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS course_publications (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      course_key TEXT NOT NULL,
      lesson_no INTEGER NOT NULL,
      telegram_chat_id TEXT,
      telegram_message_id TEXT,
      status TEXT,
      error TEXT,
      created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    con.commit()


def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def export_all_to_backup() -> Dict[str, Any]:
    with db() as con:
        courses = rows_to_dicts(con.execute("SELECT * FROM course_projects ORDER BY id").fetchall())
        lessons = rows_to_dicts(con.execute("SELECT * FROM course_lessons ORDER BY course_key, lesson_no").fetchall())
        assets = rows_to_dicts(con.execute("SELECT * FROM course_assets ORDER BY course_key, lesson_no, id").fetchall())
        publications = rows_to_dicts(con.execute("SELECT * FROM course_publications ORDER BY id").fetchall())

    payload = {
        "format": "courses_full_v1",
        "exported_at": now_iso(),
        "counts": {
            "courses": len(courses),
            "lessons": len(lessons),
            "assets": len(assets),
            "publications": len(publications),
        },
        "courses": courses,
        "lessons": lessons,
        "assets": assets,
        "publications": publications,
    }

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    latest_path = BACKUP_DIR / "courses-latest.json"
    full_path = BACKUP_DIR / "courses-full-backup.json"

    latest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    full_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    # folder backup: course / lesson_1 / files
    for course in courses:
        course_key = course["course_key"]
        course_dir = BACKUP_DIR / course_key
        course_dir.mkdir(parents=True, exist_ok=True)
        (course_dir / "course.json").write_text(json.dumps(course, ensure_ascii=False, indent=2), encoding="utf-8")

        course_lessons = [x for x in lessons if x["course_key"] == course_key]
        for lesson in course_lessons:
            lesson_no = int(lesson["lesson_no"])
            lesson_dir = course_dir / f"lesson_{lesson_no}"
            assets_dir = lesson_dir / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)

            (lesson_dir / "lesson.json").write_text(json.dumps(lesson, ensure_ascii=False, indent=2), encoding="utf-8")
            (lesson_dir / "lecture.md").write_text(lesson.get("lecture_text") or "", encoding="utf-8")
            (lesson_dir / "telegram_post.txt").write_text(lesson.get("telegram_post_text") or "", encoding="utf-8")

            for a in [x for x in assets if x["course_key"] == course_key and int(x["lesson_no"]) == lesson_no]:
                src = BASE_DIR / (a.get("file_path") or "")
                if src.exists() and src.is_file():
                    dst = assets_dir / src.name
                    try:
                        shutil.copy2(src, dst)
                    except Exception:
                        pass

    return payload


def restore_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not payload or payload.get("format") != "courses_full_v1":
        raise HTTPException(status_code=400, detail="Invalid courses backup format")

    with db() as con:
        con.execute("DELETE FROM course_publications")
        con.execute("DELETE FROM course_assets")
        con.execute("DELETE FROM course_lessons")
        con.execute("DELETE FROM course_projects")

        for c in payload.get("courses", []):
            con.execute("""
                INSERT OR REPLACE INTO course_projects
                (course_key, title, description, telegram_chat_id, telegram_channel_url, ai_system_prompt, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                c.get("course_key"), c.get("title"), c.get("description"),
                c.get("telegram_chat_id"), c.get("telegram_channel_url"),
                c.get("ai_system_prompt"), c.get("status") or "draft",
                c.get("created_at") or now_iso(), c.get("updated_at") or now_iso()
            ))

        for l in payload.get("lessons", []):
            con.execute("""
                INSERT OR REPLACE INTO course_lessons
                (course_key, lesson_no, title, topic, ai_prompt, lecture_text, telegram_post_text, status, published_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                l.get("course_key"), l.get("lesson_no"), l.get("title"), l.get("topic"),
                l.get("ai_prompt"), l.get("lecture_text"), l.get("telegram_post_text"),
                l.get("status") or "draft", l.get("published_at"),
                l.get("created_at") or now_iso(), l.get("updated_at") or now_iso()
            ))

        for a in payload.get("assets", []):
            con.execute("""
                INSERT INTO course_assets
                (course_key, lesson_no, asset_type, file_name, file_path, mime_type, size_bytes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                a.get("course_key"), a.get("lesson_no"), a.get("asset_type"),
                a.get("file_name"), a.get("file_path"), a.get("mime_type"),
                a.get("size_bytes"), a.get("created_at") or now_iso()
            ))

        for p in payload.get("publications", []):
            con.execute("""
                INSERT INTO course_publications
                (course_key, lesson_no, telegram_chat_id, telegram_message_id, status, error, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                p.get("course_key"), p.get("lesson_no"), p.get("telegram_chat_id"),
                p.get("telegram_message_id"), p.get("status"), p.get("error"),
                p.get("created_at") or now_iso()
            ))

        con.commit()

    return export_all_to_backup()


class CourseCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    telegram_chat_id: Optional[str] = ""
    telegram_channel_url: Optional[str] = ""
    ai_system_prompt: Optional[str] = ""


class CourseSave(BaseModel):
    course_key: str
    title: Optional[str] = None
    description: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    telegram_channel_url: Optional[str] = None
    ai_system_prompt: Optional[str] = None
    status: Optional[str] = None


class LessonSave(BaseModel):
    course_key: str
    lesson_no: int
    title: Optional[str] = ""
    topic: Optional[str] = ""
    ai_prompt: Optional[str] = ""
    lecture_text: Optional[str] = ""
    telegram_post_text: Optional[str] = ""
    status: Optional[str] = "draft"


@router.get("")
def list_courses():
    with db() as con:
        courses = rows_to_dicts(con.execute("""
            SELECT c.*,
              (SELECT COUNT(*) FROM course_lessons l WHERE l.course_key = c.course_key) AS lessons_count
            FROM course_projects c
            ORDER BY c.id DESC
        """).fetchall())
    return {"ok": True, "courses": courses}


@router.post("/create")
def create_course(body: CourseCreate):
    key = slugify(body.title)
    with db() as con:
        exists = con.execute("SELECT 1 FROM course_projects WHERE course_key=?", (key,)).fetchone()
        if exists:
            key = f"{key}_{int(datetime.utcnow().timestamp())}"

        con.execute("""
            INSERT INTO course_projects
            (course_key, title, description, telegram_chat_id, telegram_channel_url, ai_system_prompt, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, ?)
        """, (
            key, body.title, body.description, body.telegram_chat_id,
            body.telegram_channel_url, body.ai_system_prompt, now_iso(), now_iso()
        ))
        con.commit()

    export_all_to_backup()
    return {"ok": True, "course_key": key}


@router.post("/save")
def save_course(body: CourseSave):
    with db() as con:
        row = con.execute("SELECT * FROM course_projects WHERE course_key=?", (body.course_key,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Course not found")

        current = dict(row)
        con.execute("""
            UPDATE course_projects SET
              title=?,
              description=?,
              telegram_chat_id=?,
              telegram_channel_url=?,
              ai_system_prompt=?,
              status=?,
              updated_at=?
            WHERE course_key=?
        """, (
            body.title if body.title is not None else current.get("title"),
            body.description if body.description is not None else current.get("description"),
            body.telegram_chat_id if body.telegram_chat_id is not None else current.get("telegram_chat_id"),
            body.telegram_channel_url if body.telegram_channel_url is not None else current.get("telegram_channel_url"),
            body.ai_system_prompt if body.ai_system_prompt is not None else current.get("ai_system_prompt"),
            body.status if body.status is not None else current.get("status"),
            now_iso(),
            body.course_key
        ))
        con.commit()

    export_all_to_backup()
    return {"ok": True}


@router.get("/{course_key}")
def get_course(course_key: str):
    with db() as con:
        course = con.execute("SELECT * FROM course_projects WHERE course_key=?", (course_key,)).fetchone()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        lessons = rows_to_dicts(con.execute("""
            SELECT * FROM course_lessons WHERE course_key=? ORDER BY lesson_no
        """, (course_key,)).fetchall())

        assets = rows_to_dicts(con.execute("""
            SELECT * FROM course_assets WHERE course_key=? ORDER BY lesson_no, id
        """, (course_key,)).fetchall())

    return {
        "ok": True,
        "course": dict(course),
        "lessons": lessons,
        "assets": assets,
    }


@router.post("/lesson/save")
def save_lesson(body: LessonSave):
    if body.lesson_no < 1:
        raise HTTPException(status_code=400, detail="lesson_no must be >= 1")

    with db() as con:
        course = con.execute("SELECT 1 FROM course_projects WHERE course_key=?", (body.course_key,)).fetchone()
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        con.execute("""
            INSERT INTO course_lessons
            (course_key, lesson_no, title, topic, ai_prompt, lecture_text, telegram_post_text, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(course_key, lesson_no) DO UPDATE SET
              title=excluded.title,
              topic=excluded.topic,
              ai_prompt=excluded.ai_prompt,
              lecture_text=excluded.lecture_text,
              telegram_post_text=excluded.telegram_post_text,
              status=excluded.status,
              updated_at=excluded.updated_at
        """, (
            body.course_key, body.lesson_no, body.title, body.topic, body.ai_prompt,
            body.lecture_text, body.telegram_post_text, body.status or "draft",
            now_iso(), now_iso()
        ))
        con.commit()

    export_all_to_backup()
    return {"ok": True}


@router.post("/assets/upload")
async def upload_asset(
    course_key: str = Form(...),
    lesson_no: int = Form(...),
    asset_type: str = Form("document"),
    file: UploadFile = File(...)
):
    safe_course = slugify(course_key)
    lesson_dir = UPLOAD_DIR / safe_course / f"lesson_{lesson_no}"
    lesson_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r"[^a-zA-Z0-9а-яА-ЯіїєґІЇЄҐ_.-]+", "_", file.filename or "asset.bin")
    dst = lesson_dir / safe_name

    content = await file.read()
    dst.write_bytes(content)

    rel_path = str(dst.relative_to(BASE_DIR))

    with db() as con:
        con.execute("""
            INSERT INTO course_assets
            (course_key, lesson_no, asset_type, file_name, file_path, mime_type, size_bytes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            course_key, lesson_no, asset_type, safe_name, rel_path,
            file.content_type, len(content), now_iso()
        ))
        con.commit()

    export_all_to_backup()
    return {"ok": True, "file_path": rel_path, "file_name": safe_name}


@router.get("/backup/export")
def backup_export():
    payload = export_all_to_backup()
    return {"ok": True, "backup": payload}


@router.post("/backup/auto_save_all")
def backup_auto_save_all():
    payload = export_all_to_backup()
    return {"ok": True, "counts": payload.get("counts"), "path": str(BACKUP_DIR / "courses-latest.json")}


@router.get("/backup/counts")
def backup_counts():
    p = BACKUP_DIR / "courses-latest.json"
    if not p.exists():
        return {"ok": True, "exists": False, "counts": {}}
    payload = json.loads(p.read_text(encoding="utf-8"))
    return {"ok": True, "exists": True, "counts": payload.get("counts", {}), "exported_at": payload.get("exported_at")}


@router.post("/restore/from_static_backup")
def restore_from_static_backup():
    p = BACKUP_DIR / "courses-latest.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="courses-latest.json not found")
    payload = json.loads(p.read_text(encoding="utf-8"))
    restored = restore_from_payload(payload)
    return {"ok": True, "counts": restored.get("counts")}




@router.get("/telegram/targets")
def telegram_targets():
    """
    Повертає список Telegram каналів/чатів для select у Courses.
    """

    targets = []

    try:
        tg_backup = BASE_DIR / "backups" / "telegram-latest.json"

        if tg_backup.exists():
            payload = json.loads(tg_backup.read_text(encoding="utf-8"))

            chats = (
                payload.get("chats")
                or payload.get("groups")
                or payload.get("targets")
                or payload.get("channels")
                or []
            )

            for ch in chats:
                title = (
                    ch.get("title")
                    or ch.get("name")
                    or ch.get("chat_title")
                    or ch.get("username")
                    or "Telegram target"
                )

                chat_id = (
                    ch.get("chat_id")
                    or ch.get("target_chat_id")
                    or ch.get("id")
                    or ""
                )

                username = ch.get("username") or ""

                if not chat_id:
                    continue

                targets.append({
                    "title": title,
                    "chat_id": str(chat_id),
                    "username": username,
                })

    except Exception as e:
        return {"ok": False, "error": str(e), "targets": []}

    # dedupe
    uniq = {}
    for t in targets:
        uniq[str(t["chat_id"])] = t

    return {
        "ok": True,
        "targets": list(uniq.values())
    }
