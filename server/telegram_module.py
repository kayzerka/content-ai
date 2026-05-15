import os
import sqlite3
import requests
from datetime import datetime
from fastapi import APIRouter, Body

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

DB_PATH = os.getenv("TELEGRAM_DB_PATH", os.path.join(os.getcwd(), "data", "telegram.sqlite"))


def db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def init_telegram_db():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS telegram_chats (
        chat_id TEXT PRIMARY KEY,
        type TEXT,
        title TEXT,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        enabled INTEGER DEFAULT 1,
        role TEXT DEFAULT 'subscriber',
        created_at TEXT,
        updated_at TEXT
    )
    """)

    # TELEGRAM_CHATS_TOPIC_COLUMNS_MIGRATION_V1
    for col, ddl in [
        ("thread_id", "ALTER TABLE telegram_chats ADD COLUMN thread_id TEXT"),
        ("parent_chat_id", "ALTER TABLE telegram_chats ADD COLUMN parent_chat_id TEXT"),
        ("is_topic", "ALTER TABLE telegram_chats ADD COLUMN is_topic INTEGER DEFAULT 0"),
    ]:
        try:
            cur.execute(ddl)
        except Exception:
            pass

    cur.execute("""
    CREATE TABLE IF NOT EXISTS telegram_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_chat_id TEXT,
        title TEXT,
        text TEXT NOT NULL,
        status TEXT DEFAULT 'draft',
        scheduled_at TEXT,
        published_at TEXT,
        error TEXT,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS telegram_funnels (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        enabled INTEGER DEFAULT 1,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS telegram_funnel_steps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        funnel_id INTEGER,
        step_order INTEGER,
        title TEXT,
        message_type TEXT,
        prompt TEXT,
        delay_hours INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS telegram_scheduled_posts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        target_chat_id TEXT,
        thread_id TEXT,
        text TEXT,
        title TEXT,
        status TEXT DEFAULT 'pending',
        scheduled_at TEXT,
        published_at TEXT,
        error TEXT,
        confirmed INTEGER DEFAULT 0,
        payload_json TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT
    )
    """)

    con.commit()
    con.close()


def token():
    return (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("BOT_TOKEN")
        or os.getenv("TG_BOT_TOKEN")
        or ""
    ).strip()


def send_to_chat(chat_id: str, text: str, thread_id: str = None):
    t = token()
    if not t:
        return {"ok": False, "error": "missing_token"}

    url = f"https://api.telegram.org/bot{t}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if thread_id:
        payload["message_thread_id"] = int(thread_id)

    r = requests.post(url, data=payload, timeout=20)

    try:
        return r.json()
    except Exception:
        return {"ok": False, "raw": r.text}


def save_chat_from_update(message: dict):
    chat = message.get("chat") or {}
    user = message.get("from") or {}
    chat_id = str(chat.get("id") or "")
    thread_id = message.get("message_thread_id")
    is_topic = 1 if thread_id else 0

    if not chat_id:
        return None

    now = datetime.utcnow().isoformat()

    con = db()
    cur = con.cursor()
    cur.execute("""
    INSERT INTO telegram_chats (
        chat_id, type, title, username, first_name, last_name,
        enabled, role, created_at, updated_at, thread_id, parent_chat_id, is_topic
    )
    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(chat_id) DO UPDATE SET
        type=excluded.type,
        title=excluded.title,
        username=excluded.username,
        first_name=excluded.first_name,
        last_name=excluded.last_name,
        updated_at=excluded.updated_at,
        thread_id=excluded.thread_id,
        parent_chat_id=excluded.parent_chat_id,
        is_topic=excluded.is_topic
    """, (
        chat_id,
        chat.get("type"),
        chat.get("title"),
        chat.get("username") or user.get("username"),
        chat.get("first_name") or user.get("first_name"),
        chat.get("last_name") or user.get("last_name"),
        "group" if chat.get("type") in ("group", "supergroup", "channel") else "subscriber",
        now,
        now,
        str(thread_id) if thread_id else None,
        chat_id if thread_id else None,
        is_topic,
    ))
    con.commit()
    con.close()
    return chat_id


@router.get("/status")
def telegram_status():
    t = token()

    con = db()
    rows = con.execute("SELECT COUNT(*) AS c FROM telegram_chats WHERE enabled=1").fetchone()
    con.close()

    return {
        "ok": True,
        "configured": bool(t),
        "telegram_configured": bool(t),
        "enabled_chats": rows["c"] if rows else 0,
    }


@router.get("/chats")
def telegram_chats():
    con = db()
    rows = con.execute("""
        SELECT * FROM telegram_chats
        ORDER BY updated_at DESC
    """).fetchall()
    con.close()
    return {"ok": True, "chats": [dict(r) for r in rows]}


@router.post("/chats/{chat_id}/toggle")
def telegram_toggle_chat(chat_id: str, payload: dict = Body(default={})):
    enabled = 1 if payload.get("enabled", True) else 0
    con = db()
    con.execute(
        "UPDATE telegram_chats SET enabled=?, updated_at=? WHERE chat_id=?",
        (enabled, datetime.utcnow().isoformat(), chat_id),
    )
    con.commit()
    con.close()
    return {"ok": True, "chat_id": chat_id, "enabled": bool(enabled)}


@router.post("/send")
def telegram_send(payload: dict = Body(default={})):
    text = payload.get("text") or payload.get("message") or ""
    chat_ids = payload.get("chat_ids") or []
    thread_id = payload.get("thread_id")

    if not text:
        return {"ok": False, "error": "empty_text"}

    con = db()

    if not chat_ids:
        rows = con.execute("""
            SELECT chat_id FROM telegram_chats
            WHERE enabled=1
        """).fetchall()
        chat_ids = [r["chat_id"] for r in rows]

    con.close()

    results = []
    for cid in chat_ids:
        data = send_to_chat(str(cid), text, thread_id=thread_id)
        results.append({
            "chat_id": str(cid),
            "ok": bool(data.get("ok")),
            "telegram": data,
        })

    return {
        "ok": any(r["ok"] for r in results),
        "sent_count": sum(1 for r in results if r["ok"]),
        "results": results,
    }


@router.post("/send_message")
def telegram_send_message_alias(payload: dict = Body(default={})):
    return telegram_send(payload)


@router.post("/send_message_multi_v3")
def telegram_send_message_multi_v3(payload: dict = Body(default={})):
    return telegram_send(payload)


@router.get("/updates")
def telegram_updates():
    t = token()
    if not t:
        return {"ok": False, "error": "missing_token"}

    r = requests.get(f"https://api.telegram.org/bot{t}/getUpdates", timeout=20)
    data = r.json()

    saved = []
    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("channel_post")
        if not msg:
            continue

        chat_id = save_chat_from_update(msg)
        saved_msg = save_message_from_update(msg)

        if chat_id:
            saved.append(chat_id)

            txt = msg.get("text") or ""
            if txt.startswith("/start") or txt.startswith("/register"):
                send_to_chat(chat_id, "✅ Бот підключено. Чат зареєстровано в Telegram Center.", thread_id=msg.get("message_thread_id"))

    return {
        "ok": True,
        "saved_chats": list(dict.fromkeys(saved)),
        "raw_count": len(data.get("result", [])),
    }


@router.post("/posts")
def telegram_create_post(payload: dict = Body(default={})):
    text = payload.get("text") or ""
    title = payload.get("title") or ""
    target_chat_id = payload.get("target_chat_id")
    scheduled_at = payload.get("scheduled_at")
    thread_id = payload.get("thread_id")
    status = "scheduled" if scheduled_at else "draft"

    if not text:
        return {"ok": False, "error": "empty_text"}

    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO telegram_posts (
            target_chat_id, title, text, status, scheduled_at, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        target_chat_id,
        title,
        text,
        status,
        scheduled_at,
        datetime.utcnow().isoformat(),
    ))
    con.commit()
    post_id = cur.lastrowid
    con.close()

    return {"ok": True, "post_id": post_id, "status": status}


@router.get("/posts")
def telegram_list_posts():
    con = db()
    rows = con.execute("""
        SELECT * FROM telegram_posts
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()
    con.close()
    return {"ok": True, "posts": [dict(r) for r in rows]}


@router.post("/posts/{post_id}/publish")
def telegram_publish_post(post_id: int):
    con = db()
    post = con.execute("SELECT * FROM telegram_posts WHERE id=?", (post_id,)).fetchone()

    if not post:
        con.close()
        return {"ok": False, "error": "post_not_found"}

    chat_ids = []
    if post["target_chat_id"]:
        chat_ids = [post["target_chat_id"]]
    else:
        rows = con.execute("SELECT chat_id FROM telegram_chats WHERE enabled=1").fetchall()
        chat_ids = [r["chat_id"] for r in rows]

    results = []
    for cid in chat_ids:
        data = send_to_chat(str(cid), post["text"])
        results.append({"chat_id": str(cid), "ok": bool(data.get("ok")), "telegram": data})

    ok = any(r["ok"] for r in results)
    con.execute("""
        UPDATE telegram_posts
        SET status=?, published_at=?, error=?
        WHERE id=?
    """, (
        "published" if ok else "failed",
        datetime.utcnow().isoformat() if ok else None,
        None if ok else str(results),
        post_id,
    ))
    con.commit()
    con.close()

    return {
        "ok": ok,
        "sent_count": sum(1 for r in results if r["ok"]),
        "results": results,
    }



# === SCHEDULER POSTS ===

@router.post("/schedule")
def telegram_create_schedule(payload: dict = Body(default={})):
    target_chat_id = payload.get("target_chat_id") or payload.get("chat_id")
    control_chat_ids = payload.get("control_chat_ids") or [payload.get("control_chat_id") or target_chat_id]
    import json
    control_chat_ids_json = json.dumps(control_chat_ids)
    text = payload.get("text")
    scheduled_at = payload.get("scheduled_at")
    thread_id = payload.get("thread_id")

    if not target_chat_id or not text:
        return {"ok": False, "error": "missing_fields"}

    con = db()
    cur = con.cursor()

    from datetime import datetime, timedelta

    now = datetime.utcnow()
    confirm_until = (now).isoformat()

    cur.execute("""
    INSERT INTO telegram_scheduled_posts (
        chat_id, control_chat_ids, thread_id, text, status, scheduled_at, confirm_until,
        confirmed, created_at, updated_at
    )
    VALUES (?, ?, ?, ?, 'pending_confirm', ?, ?, 0, ?, ?)
    """, (
        target_chat_id,
        control_chat_ids_json,
        thread_id,
        text,
        scheduled_at,
        confirm_until,
        now.isoformat(),
        now.isoformat()
    ))

    post_id = cur.lastrowid
    con.commit()
    con.close()

    return {"ok": True, "post_id": post_id}


@router.get("/schedule")
def telegram_list_schedule():
    con = db()
    rows = con.execute("""
        SELECT * FROM telegram_scheduled_posts
        ORDER BY id DESC
        LIMIT 200
    """).fetchall()
    con.close()

    return {"ok": True, "items": [dict(r) for r in rows]}


@router.post("/schedule/{post_id}/confirm")
def telegram_confirm(post_id: int):
    con = db()

    post = con.execute(
        "SELECT * FROM telegram_scheduled_posts WHERE id=?",
        (post_id,)
    ).fetchone()

    if not post:
        con.close()
        return {"ok": False, "error": "not_found"}

    con.execute("""
        UPDATE telegram_scheduled_posts
        SET confirmed=1, status='scheduled', updated_at=datetime('now')
        WHERE id=?
    """, (post_id,))

    con.commit()
    con.close()

    return {"ok": True, "post_id": post_id}


@router.post("/schedule/{post_id}/cancel")
def telegram_cancel(post_id: int):
    con = db()

    con.execute("""
        UPDATE telegram_scheduled_posts
        SET status='cancelled', updated_at=datetime('now')
        WHERE id=?
    """, (post_id,))

    con.commit()
    con.close()

    return {"ok": True}


# === /SCHEDULER POSTS ===



def send_confirm_message(chat_id: str, post_id: int, text: str):
    t = token()
    if not t:
        return {"ok": False}

    import json

    keyboard = {
        "inline_keyboard": [[
            {"text": "✅ Confirm", "callback_data": f"confirm:{post_id}"},
            {"text": "❌ Cancel", "callback_data": f"cancel:{post_id}"}
        ]]
    }

    url = f"https://api.telegram.org/bot{t}/sendMessage"

    return requests.post(url, data={
        "chat_id": chat_id,
        "text": f"⏰ Підтверди пост:\n\n{text}",
        "reply_markup": json.dumps(keyboard)
    }).json()



@router.get("/updates_poll")
def telegram_poll_updates():
    t = token()
    if not t:
        return {"ok": False}

    r = requests.get(f"https://api.telegram.org/bot{t}/getUpdates")
    data = r.json()

    for upd in data.get("result", []):
        cb = upd.get("callback_query")
        if not cb:
            continue

        data_str = cb.get("data") or ""
        msg = cb.get("message") or {}
        chat_id = str(msg.get("chat", {}).get("id"))

        if ":" in data_str:
            action, post_id = data_str.split(":")

            if action == "confirm":
                telegram_confirm(int(post_id))
                send_to_chat(chat_id, "✅ Пост підтверджено")

            elif action == "cancel":
                telegram_cancel(int(post_id))
                send_to_chat(chat_id, "❌ Пост скасовано")

    return {"ok": True}



def run_scheduler():
    init_telegram_db()
    from datetime import datetime
    now = datetime.utcnow().isoformat()

    con = db()

    # 1. Відправити confirm якщо pending
    rows = con.execute("""
        SELECT * FROM telegram_scheduled_posts
        WHERE status='pending_confirm'
    """).fetchall()

    for r in rows:
        import json
        admins = json.loads(r["control_chat_ids"] or "[]")

        for admin_id in admins:
            send_confirm_message(admin_id, r["id"], r["text"])

        con.execute("""
            UPDATE telegram_scheduled_posts
            SET status='waiting_user', updated_at=datetime('now')
            WHERE id=?
        """, (r["id"],))

    # 2. Публікація
    rows = con.execute("""
        SELECT * FROM telegram_scheduled_posts
        WHERE status='scheduled'
        AND scheduled_at <= ?
    """, (now,)).fetchall()

    for r in rows:
        send_to_chat(r["chat_id"], r["text"], thread_id=r["thread_id"])

        con.execute("""
            UPDATE telegram_scheduled_posts
            SET status='published', updated_at=datetime('now')
            WHERE id=?
        """, (r["id"],))

    con.commit()
    con.close()


import threading, time

def start_scheduler_loop():
    def loop():
        while True:
            try:
                run_scheduler()
            except Exception as e:
                print("scheduler error:", e)
            time.sleep(30)

    t = threading.Thread(target=loop, daemon=True)
    t.start()

start_scheduler_loop()

# === TELEGRAM CALLBACK AUTO POLLER V1 ===

def answer_callback_query(callback_id: str, text: str = ""):
    t = token()
    if not t or not callback_id:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{t}/answerCallbackQuery",
            data={
                "callback_query_id": callback_id,
                "text": text or "Готово",
                "show_alert": False,
            },
            timeout=10,
        )
    except Exception as e:
        print("[telegram callback answer error]", e)


def process_telegram_callbacks_once():
    t = token()
    if not t:
        return {"ok": False, "error": "missing_token"}

    r = requests.get(f"https://api.telegram.org/bot{t}/getUpdates", timeout=20)
    data = r.json()

    processed = 0

    for upd in data.get("result", []):
        cb = upd.get("callback_query")
        if not cb:
            continue

        processed += 1

        callback_id = cb.get("id")
        data_str = cb.get("data") or ""
        msg = cb.get("message") or {}
        chat_id = str(msg.get("chat", {}).get("id") or "")

        if ":" not in data_str:
            answer_callback_query(callback_id, "Невідома дія")
            continue

        action, post_id = data_str.split(":", 1)

        if action == "confirm":
            con = db()
            post = con.execute(
                "SELECT confirmed FROM telegram_scheduled_posts WHERE id=?",
                (post_id,)
            ).fetchone()

            if post and post["confirmed"] == 1:
                answer_callback_query(callback_id, "Вже підтверджено іншим адміном")
                send_to_chat(chat_id, "⚠️ Вже підтверджено іншим адміном")
            else:
                telegram_confirm(int(post_id))
                answer_callback_query(callback_id, "Пост підтверджено")
                send_to_chat(chat_id, "✅ Пост підтверджено")
            con.close()

        elif action == "cancel":
            telegram_cancel(int(post_id))
            answer_callback_query(callback_id, "Пост скасовано")
            send_to_chat(chat_id, "❌ Пост скасовано")

    return {"ok": True, "processed": processed}


@router.get("/callbacks_poll")
def telegram_callbacks_poll():
    return process_telegram_callbacks_once()


import threading
import time

def start_callback_poller_loop():
    def loop():
        while True:
            try:
                process_telegram_callbacks_once()
            except Exception as e:
                print("[telegram callback poller error]", e)
            time.sleep(3)

    th = threading.Thread(target=loop, daemon=True)
    th.start()

start_callback_poller_loop()

# === /TELEGRAM CALLBACK AUTO POLLER V1 ===

# === TELEGRAM MESSAGE INGEST V1 ===

def save_message_from_update(message: dict):
    import json
    from datetime import datetime

    chat = message.get("chat") or {}
    user = message.get("from") or {}

    chat_id = str(chat.get("id") or "")
    thread_id = message.get("message_thread_id")
    message_id = message.get("message_id")
    text = message.get("text") or message.get("caption") or ""

    if not chat_id or not message_id:
        return None

    # не зберігаємо службові пусті повідомлення без тексту
    if not text:
        return None

    from_name = " ".join(
        x for x in [
            user.get("first_name"),
            user.get("last_name"),
        ] if x
    )

    date_ts = message.get("date")
    date_iso = None
    if date_ts:
        try:
            date_iso = datetime.utcfromtimestamp(int(date_ts)).isoformat()
        except Exception:
            date_iso = None

    con = db()
    con.execute("""
        INSERT OR IGNORE INTO telegram_messages (
            chat_id, thread_id, message_id,
            from_id, from_name, username,
            text, date_ts, date_iso, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        chat_id,
        str(thread_id) if thread_id else None,
        int(message_id),
        str(user.get("id")) if user.get("id") else None,
        from_name,
        user.get("username"),
        text,
        int(date_ts) if date_ts else None,
        date_iso,
        json.dumps(message, ensure_ascii=False),
    ))
    con.commit()
    con.close()

    return {
        "chat_id": chat_id,
        "thread_id": str(thread_id) if thread_id else None,
        "message_id": message_id,
    }


@router.get("/messages")
def telegram_list_messages(chat_id: str = None, thread_id: str = None, limit: int = 100):
    con = db()

    where = []
    params = []

    if chat_id:
        where.append("chat_id=?")
        params.append(chat_id)

    if thread_id:
        where.append("thread_id=?")
        params.append(thread_id)

    sql = """
        SELECT * FROM telegram_messages
    """

    if where:
        sql += " WHERE " + " AND ".join(where)

    sql += " ORDER BY date_ts DESC, id DESC LIMIT ?"
    params.append(int(limit))

    con.execute("""
        CREATE TABLE IF NOT EXISTS telegram_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            thread_id TEXT,
            message_id TEXT,
            from_id TEXT,
            from_username TEXT,
            text TEXT,
            date TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    rows = con.execute(sql, params).fetchall()
    con.close()

    return {
        "ok": True,
        "messages": [dict(r) for r in rows],
    }


@router.get("/messages/summary")
def telegram_messages_summary():
    con = db()
    rows = con.execute("""
        SELECT
            chat_id,
            thread_id,
            COUNT(*) AS messages_count,
            MAX(date_iso) AS last_message_at
        FROM telegram_messages
        GROUP BY chat_id, thread_id
        ORDER BY last_message_at DESC
    """).fetchall()
    con.close()

    return {
        "ok": True,
        "items": [dict(r) for r in rows],
    }

# === /TELEGRAM MESSAGE INGEST V1 ===

# === TELEGRAM AI OPENAI POLISH V1 ===

def _telegram_call_openai(prompt: str):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini").strip()
    base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1").rstrip("/")

    if not api_key:
        return {
            "ok": False,
            "error": "missing_openai_key",
            "text": None,
        }

    try:
        r = requests.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Ти фінальний редактор Telegram-контенту у стилі Даші Побережної. "
                            "Твоє завдання — прибрати AI-шаблонність, зробити текст живим, точним, "
                            "емоційним, з характером, але без пафосу і без води."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.75,
            },
            timeout=90,
        )

        data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content")

        return {
            "ok": bool(text),
            "text": text,
            "raw": data,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "text": None,
        }


def _telegram_polish_dasha_style(draft_text: str, original_prompt: str = ""):
    polish_prompt = f"""
Ось чорновий контент-план / тексти, згенеровані DeepSeek.

Твоє завдання:
переписати фінально у стилі Даші Побережної.

НЕ змінюй змістову логіку, але:
- прибери AI-шаблонність;
- зроби текст живішим;
- додай характер, стан, позицію;
- залиш короткі абзаци;
- не роби сухий маркетинг;
- не роби мотиваційний шлак;
- збережи структуру по днях;
- якщо є продаж — зроби його людським, але чітким.

Оригінальний запит:
{original_prompt[:4000]}

Чернетка:
{draft_text}
"""
    return _telegram_call_openai(polish_prompt)

# === /TELEGRAM AI OPENAI POLISH V1 ===

# === TELEGRAM AI GENERATE PLAN ROUTE V2 ===

def _telegram_get_recent_messages_for_ai(chat_id: str, thread_id: str | None = None, limit: int = 80):
    import sqlite3

    con = sqlite3.connect(_telegram_db_path_v1())
    con.row_factory = sqlite3.Row
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS telegram_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                thread_id TEXT,
                message_id TEXT,
                from_id TEXT,
                from_username TEXT,
                text TEXT,
                date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        params = [str(chat_id)]
        sql = """
            SELECT text, from_username, date, created_at
            FROM telegram_messages
            WHERE chat_id = ?
        """

        if thread_id:
            sql += " AND thread_id = ?"
            params.append(str(thread_id))

        sql += " ORDER BY COALESCE(date, created_at) DESC LIMIT ?"
        params.append(int(limit or 80))

        rows = con.execute(sql, params).fetchall()
        rows = list(reversed(rows))

        lines = []
        for r in rows:
            text = (r["text"] or "").strip()
            if not text:
                continue
            who = r["from_username"] or "user"
            lines.append(f"{who}: {text}")

        return "\n".join(lines)
    finally:
        con.close()


def telegram_ai_generate_plan(payload: dict = Body(default={})):
    chat_id = payload.get("chat_id") or payload.get("target_chat_id")
    thread_id = payload.get("thread_id")
    topic = payload.get("topic") or "контент-план для Telegram-групи"
    days = int(payload.get("days") or 7)
    style_types = payload.get("style_types") or ["MEANING", "PRACTICAL", "DEPTH"]
    post_type = payload.get("post_type") or "argument"
    ai_mode = payload.get("ai_mode") or os.getenv("TELEGRAM_AI_MODE", "deepseek_draft_openai_polish")

    if not chat_id:
        return {"ok": False, "error": "missing_chat_id"}

    context = _telegram_get_recent_messages_for_ai(
        chat_id=str(chat_id),
        thread_id=str(thread_id) if thread_id else None,
        limit=int(payload.get("limit") or 80),
    )

    prompt = f"""
Ти генеруєш Telegram-контент у стилі Даші Побережної.

Тема:
{topic}

Період:
{days} днів

Характер / стилі:
{", ".join(style_types)}

Тип поста:
{post_type}

Контекст реальних повідомлень групи:
{context if context else "Поки немає збережених повідомлень. Генеруй без контексту групи."}

Завдання:
1. Коротко проаналізуй контекст групи.
2. Запропонуй план на {days} днів.
3. Для кожного дня дай:
   - тему;
   - тип повідомлення;
   - характер стилю;
   - готовий Telegram-текст;
   - CTA, якщо доречно.

Правила:
- українською;
- живо, не як AI;
- короткі абзаци;
- у стилі Даші: стан, сенс, позиція, глибина;
- без мотиваційного шлаку.
"""

    draft_ai = _telegram_call_ai(prompt)
    draft_text = draft_ai.get("text")

    final_ai = None
    final_text = draft_text

    if ai_mode in ("openai_polish", "deepseek_draft_openai_polish") and draft_text:
        final_ai = _telegram_polish_dasha_style(draft_text, original_prompt=prompt)
        if final_ai.get("ok") and final_ai.get("text"):
            final_text = final_ai.get("text")

    return {
        "ok": bool(final_text),
        "ai_mode": ai_mode,
        "chat_id": chat_id,
        "thread_id": thread_id,
        "messages_used": len(context.splitlines()) if context else 0,
        "draft_provider": "deepseek",
        "draft_text": draft_text,
        "draft_ai": draft_ai,
        "polish_provider": "openai" if final_ai else None,
        "polish_ai": final_ai,
        "text": final_text,
        "final_text": final_text,
        "prompt": prompt,
    }

# === /TELEGRAM AI GENERATE PLAN ROUTE V2 ===

# === TELEGRAM AI DEEPSEEK CALL FIX V1 ===

def _telegram_call_ai(prompt: str):
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
    base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").rstrip("/")

    if not api_key:
        return {
            "ok": False,
            "error": "missing_deepseek_key",
            "text": None,
        }

    try:
        r = requests.post(
            f"{base}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Ти Telegram-контент-стратег. "
                            "Аналізуєш групи, витягуєш теми, болі, заперечення "
                            "і створюєш чорновий контент-план українською."
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": 0.85,
            },
            timeout=90,
        )

        data = r.json()
        text = data.get("choices", [{}])[0].get("message", {}).get("content")

        return {
            "ok": bool(text),
            "text": text,
            "raw": data,
        }

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "text": None,
        }

# === /TELEGRAM AI DEEPSEEK CALL FIX V1 ===

# MANUAL_TELEGRAM_CHAT_UPSERT_RENDER_FIX_V2
@router.post("/chats/upsert")
def telegram_chat_manual_upsert(payload: dict = {}):
    init_telegram_db()

    chat_id = str(payload.get("chat_id") or "").strip()
    if not chat_id:
        return {"ok": False, "error": "chat_id_required"}

    chat_type = str(payload.get("type") or "supergroup").strip()
    title = payload.get("title")
    username = payload.get("username")
    first_name = payload.get("first_name")
    last_name = payload.get("last_name")
    enabled = int(payload.get("enabled", 1))
    role = str(payload.get("role") or "client_group").strip()
    thread_id = payload.get("thread_id")
    parent_chat_id = payload.get("parent_chat_id")
    is_topic = int(payload.get("is_topic", 0))

    import sqlite3
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        INSERT INTO telegram_chats
        (chat_id, type, title, username, first_name, last_name, enabled, role, created_at, updated_at, thread_id, parent_chat_id, is_topic)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            type=excluded.type,
            title=excluded.title,
            username=excluded.username,
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            enabled=excluded.enabled,
            role=excluded.role,
            updated_at=datetime('now'),
            thread_id=excluded.thread_id,
            parent_chat_id=excluded.parent_chat_id,
            is_topic=excluded.is_topic
    """, (
        chat_id, chat_type, title, username, first_name, last_name,
        enabled, role, thread_id, parent_chat_id, is_topic
    ))

    con.commit()
    con.close()

    return {
        "ok": True,
        "chat_id": chat_id,
        "type": chat_type,
        "title": title,
        "enabled": enabled,
        "role": role,
        "thread_id": thread_id,
        "parent_chat_id": parent_chat_id,
        "is_topic": is_topic,
    }

# MANUAL_TELEGRAM_CHAT_UPSERT_RENDER_FIX_V3_DEBUG
@router.post("/chats/upsert_v2")
def telegram_chat_manual_upsert_v2(payload: dict = {}):
    import sqlite3, traceback
    try:
        init_telegram_db()
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()

        for ddl in [
            "ALTER TABLE telegram_chats ADD COLUMN thread_id TEXT",
            "ALTER TABLE telegram_chats ADD COLUMN parent_chat_id TEXT",
            "ALTER TABLE telegram_chats ADD COLUMN is_topic INTEGER DEFAULT 0",
        ]:
            try:
                cur.execute(ddl)
            except Exception:
                pass

        chat_id = str(payload.get("chat_id") or "").strip()
        if not chat_id:
            return {"ok": False, "error": "chat_id_required"}

        cur.execute("DELETE FROM telegram_chats WHERE chat_id=?", (chat_id,))
        cur.execute("""
            INSERT INTO telegram_chats
            (chat_id, type, title, username, first_name, last_name, enabled, role, created_at, updated_at, thread_id, parent_chat_id, is_topic)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'), ?, ?, ?)
        """, (
            chat_id,
            payload.get("type") or "supergroup",
            payload.get("title"),
            payload.get("username"),
            payload.get("first_name"),
            payload.get("last_name"),
            int(payload.get("enabled", 1)),
            payload.get("role") or "client_group",
            payload.get("thread_id"),
            payload.get("parent_chat_id"),
            int(payload.get("is_topic", 0)),
        ))

        con.commit()
        con.close()
        return {"ok": True, "chat_id": chat_id}

    except Exception as e:
        return {
            "ok": False,
            "error": "upsert_v2_failed",
            "detail": repr(e),
            "trace": traceback.format_exc()[-1200:],
        }

# TELEGRAM_MODULE_DB_DEBUG_V1
@router.get("/debug/module_db")
def telegram_module_debug_db():
    import os
    con = db()
    rows = [dict(r) for r in con.execute("""
        SELECT chat_id, title, enabled, role
        FROM telegram_chats
        ORDER BY role, title, chat_id
    """).fetchall()]
    con.close()

    return {
        "ok": True,
        "db_path": DB_PATH,
        "cwd": os.getcwd(),
        "count": len(rows),
        "rows": rows,
    }

# TELEGRAM_SEED_DEFAULTS_FREE_RENDER_V1
@router.post("/chats/seed_defaults")
def telegram_seed_defaults():
    import json
    from pathlib import Path

    seed_path = Path(__file__).resolve().parent / "telegram_seed.json"
    if not seed_path.exists():
        return {"ok": False, "error": "telegram_seed_json_not_found", "path": str(seed_path)}

    items = json.loads(seed_path.read_text(encoding="utf-8"))
    results = []

    for payload in items:
        try:
            res = telegram_chat_manual_upsert_v2(payload)
            results.append(res)
        except Exception as e:
            results.append({"ok": False, "chat_id": payload.get("chat_id"), "error": repr(e)})

    return {"ok": all(bool(r.get("ok")) for r in results), "count": len(results), "results": results}
