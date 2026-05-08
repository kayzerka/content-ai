from fastapi import APIRouter, Body
import sqlite3
import os
import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env")

router = APIRouter(prefix="/api/telegram", tags=["telegram-safe"])

DB_PATH = os.getenv("TELEGRAM_DB_PATH", "db/telegram.sqlite")
INTERNAL_BOT_TOKEN = (
    os.getenv("TELEGRAM_BOT_TOKEN")
    or os.getenv("BOT_TOKEN")
    or os.getenv("TG_BOT_TOKEN")
    or ""
).strip()

CLIENT_BOT_TOKEN = (
    os.getenv("CLIENT_TELEGRAM_BOT_TOKEN")
    or INTERNAL_BOT_TOKEN
).strip()

PURPOSE_ROLE_MAP = {
    "planner_internal": ["internal_planner"],
    "internal_planner": ["internal_planner"],
    "client_funnel": ["client_channel", "client_group"],
    "client_broadcast": ["client_channel", "client_group"],
}


def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


def get_chat_ids_for_purpose(purpose: str):
    roles = PURPOSE_ROLE_MAP.get((purpose or "").strip(), [])

    if not roles:
        return []

    placeholders = ",".join(["?"] * len(roles))

    con = db()

    rows = con.execute(
        f"""
        SELECT chat_id
        FROM telegram_chats
        WHERE enabled=1
          AND role IN ({placeholders})
        """,
        roles,
    ).fetchall()

    con.close()

    return [str(r["chat_id"]) for r in rows]


def send_to_chat(chat_id: str, text: str, purpose: str = "client_funnel", thread_id: str = None):

    bot_token = CLIENT_BOT_TOKEN

    if purpose in ("planner_internal", "internal_planner"):
        bot_token = INTERNAL_BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    try:
        r = requests.post(
            url,
            json={
                "chat_id": chat_id,
                "text": text,
                **({"message_thread_id": int(thread_id)} if thread_id else {}),
            },
            timeout=30,
        )

        return r.json()

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
        }


@router.post("/send_safe")
def send_safe(payload: dict = Body(default={})):
    text = payload.get("text") or ""
    purpose = payload.get("purpose") or "client_broadcast"

    if not text:
        return {
            "ok": False,
            "error": "empty_text",
        }

    chat_ids = get_chat_ids_for_purpose(purpose)

    results = []

    for cid in chat_ids:
        tg = send_to_chat(cid, text, purpose=purpose)

        results.append({
            "chat_id": cid,
            "ok": bool(tg.get("ok")),
            "telegram": tg,
        })

    return {
        "ok": any(r["ok"] for r in results),
        "purpose": purpose,
        "sent_count": sum(1 for r in results if r["ok"]),
        "results": results,
    }


@router.get("/client_updates")
def client_bot_updates():
    token = CLIENT_BOT_TOKEN

    if not token:
        return {"ok": False, "error": "missing_client_bot_token"}

    r = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        timeout=20,
    )

    data = r.json()
    saved = []

    con = db()

    for upd in data.get("result", []):
        msg = upd.get("message") or upd.get("channel_post") or upd.get("my_chat_member")
        if not msg:
            continue

        chat = msg.get("chat") or {}
        chat_id = str(chat.get("id") or "")

        if not chat_id:
            continue

        chat_type = chat.get("type") or ""
        title = chat.get("title") or chat.get("first_name") or ""
        username = chat.get("username") or ""

        role = "client_channel" if chat_type == "channel" else "client_group"

        con.execute(
            """
            INSERT INTO telegram_chats (
                chat_id, type, title, username,
                enabled, role, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 1, ?, datetime('now'), datetime('now'))
            ON CONFLICT(chat_id) DO UPDATE SET
                type=excluded.type,
                title=excluded.title,
                username=excluded.username,
                enabled=1,
                role=excluded.role,
                updated_at=datetime('now')
            """,
            (chat_id, chat_type, title, username, role),
        )

        saved.append({
            "chat_id": chat_id,
            "type": chat_type,
            "title": title,
            "username": username,
            "role": role,
        })

    con.commit()
    con.close()

    return {
        "ok": True,
        "saved": saved,
        "raw_count": len(data.get("result", [])),
    }


# ============================================================================
# TELEGRAM TARGET AI + SCHEDULER V1
# ============================================================================

import threading
import time
from datetime import datetime

def ensure_safe_schedule_db():
    con = db()
    con.execute("""
        CREATE TABLE IF NOT EXISTS telegram_safe_scheduled_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            scheduled_at TEXT,
            target_chat_id TEXT,
            purpose TEXT,
            text TEXT,
            status TEXT DEFAULT 'scheduled',
            sent_at TEXT,
            error TEXT
        )
    """)
    con.commit()
    con.close()




CTA_STRATEGIES = {
    "subscribe": "Наприкінці мʼяко запропонуй підписатися або увімкнути сповіщення.",
    "write_direct": "Наприкінці запропонуй написати в direct / приватні повідомлення.",
    "comment_word": "Наприкінці запропонуй залишити кодове слово у коментарях.",
    "go_channel": "Наприкінці запропонуй перейти в канал або залишитися в каналі.",
    "wait_next_post": "Наприкінці запропонуй чекати наступний пост.",
    "no_cta": "Не додавай жодного CTA або заклику до дії."
}

CTA_STYLE_RULES = {
    "soft": "CTA має бути мʼяким, без тиску.",
    "neutral": "CTA має бути спокійним та природним.",
    "strong": "CTA може бути більш прямим та акцентним."
}

CTA_POSITION_RULES = {
    "soft_end": "CTA повинен бути лише в самому кінці.",
    "hard_end": "Заверши текст сильним CTA.",
    "middle": "Можна акуратно вставити CTA в середині тексту.",
    "none": "Не вставляй CTA."
}


def ai_generate_telegram_text(
    prompt: str,
    target_title: str = "",
    cta_type: str = "wait_next_post",
    cta_style: str = "soft",
    cta_position: str = "soft_end",
    cta_custom_instruction: str = "",
):
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
    base = os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com").strip()

    if not api_key:
        return "DEEPSEEK_API_KEY не встановлений у .env"

    system = (
        "Ти контент-асистент Даші — кармолога та регресолога. "

        "Пиши українською мовою природно, зріло, тепло та впевнено. "

        "СТРОГО ЗАБОРОНЕНО: "
        "сюсюкання, інфантильний стиль, псевдомістичний перегрів, "
        "фрази типу: "
        "'мої квантові частоти', "
        "'мої ріднесенькі', "
        "'душеньки', "
        "'любімочки', "
        "'мої хороші', "
        "'вібрації всесвіту', "
        "'космічні потоки', "
        "'енергії нового виміру' "
        "та інші дивні езотеричні штампи. "

        "Не пиши пафосно або крінжово. "
        "Не роби текст схожим на інфоциганський Telegram. "

        "Стиль має бути:"
        "людяний,"
        "спокійний,"
        "емоційно теплий,"
        "з довірою,"
        "без перегину. "

        "Можна використовувати нормальні звернення:"
        "'Дорогі люди', "
        "'Друзі', "
        "'Вітаю вас', "
        "'Привіт вам', "
        "'Любі друзі', "
        "'Хочу сьогодні поділитися'. "

        "ВАЖЛИВО: "
        "не використовуй звернення через слово 'мої': "
        "'мої люди', "
        "'мої хороші', "
        "'мої рідні', "
        "'мої прекрасні', "
        "'мої любі' "
        "— це звучить неприродно та штучно. "

        "Звернення мають бути спокійними, дорослими та природними."

        "Пиши так, ніби це реальна жива людина, "
        "а не езотеричний бот. "

        "Не додавай пояснення — тільки готовий текст для Telegram."
    )

    cta_rule = CTA_STRATEGIES.get(
        cta_type,
        CTA_STRATEGIES["wait_next_post"]
    )

    cta_style_rule = CTA_STYLE_RULES.get(
        cta_style,
        CTA_STYLE_RULES["soft"]
    )

    cta_position_rule = CTA_POSITION_RULES.get(
        cta_position,
        CTA_POSITION_RULES["soft_end"]
    )

    user = f"""
Куди пишемо:
{target_title or "клієнтська група/канал"}

Задача:
{prompt}

CTA СТРАТЕГІЯ:
{cta_rule}

CTA-КОНСТРУКТОР З UI:
{cta_custom_instruction or "не передано"}

СТИЛЬ CTA:
{cta_style_rule}

ПОЗИЦІЯ CTA:
{cta_position_rule}

AI НЕ МАЄ ПРАВА вигадувати власний CTA,
якого немає в правилах вище.

Згенеруй готове Telegram-повідомлення.
"""

    r = requests.post(
        base.rstrip("/") + "/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": 900,
            "stream": False,
        },
        timeout=90,
    )

    if r.status_code != 200:
        return "AI_ERROR:\n" + r.text

    data = r.json()
    return data["choices"][0]["message"]["content"].strip()


@router.post("/ai_generate_message")
def ai_generate_message(payload: dict = Body(default={})):
    prompt = str(payload.get("prompt") or "").strip()
    target_chat_id = str(payload.get("target_chat_id") or "").strip()

    cta_type = str(payload.get("cta_type") or "wait_next_post").strip()
    cta_style = str(payload.get("cta_style") or "soft").strip()
    cta_position = str(payload.get("cta_position") or "soft_end").strip()
    cta_custom_instruction = str(payload.get("cta_custom_instruction") or "").strip()

    if not prompt:
        return {"ok": False, "error": "empty_prompt"}

    target_title = ""

    if target_chat_id:
        con = db()
        row = con.execute(
            "SELECT title, username, role FROM telegram_chats WHERE chat_id=? LIMIT 1",
            (target_chat_id,),
        ).fetchone()
        con.close()

        if row:
            target_title = row["title"] or row["username"] or target_chat_id

    text = ai_generate_telegram_text(
        prompt,
        target_title=target_title,
        cta_type=cta_type,
        cta_style=cta_style,
        cta_position=cta_position,
        cta_custom_instruction=cta_custom_instruction,
    )

    return {
        "ok": True,
        "target_chat_id": target_chat_id or None,
        "result": text,
        "text": text,
    }


@router.post("/schedule_safe")
def schedule_safe(payload: dict = Body(default={})):
    ensure_safe_schedule_db()

    text = str(payload.get("text") or "").strip()
    scheduled_at = str(payload.get("scheduled_at") or "").strip()
    raw_target_chat_id = str(payload.get("target_chat_id") or payload.get("chat_id") or "").strip()
    target_chat_id = raw_target_chat_id
    thread_id = None

    if ":" in raw_target_chat_id:
        target_chat_id, thread_id = raw_target_chat_id.split(":", 1)
    purpose = str(payload.get("purpose") or "client_funnel").strip()

    if not text:
        return {"ok": False, "error": "empty_text"}

    if not scheduled_at:
        return {"ok": False, "error": "empty_scheduled_at"}

    if not target_chat_id:
        return {"ok": False, "error": "empty_target_chat_id"}

    con = db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO telegram_safe_scheduled_messages (
            created_at, scheduled_at, target_chat_id, purpose, text, status
        )
        VALUES (datetime('now'), ?, ?, ?, ?, 'scheduled')
    """, (scheduled_at, target_chat_id, purpose, text))
    schedule_id = cur.lastrowid
    con.commit()
    con.close()

    return {
        "ok": True,
        "schedule_id": schedule_id,
        "target_chat_id": raw_target_chat_id,
        "scheduled_at": scheduled_at,
    }


@router.get("/scheduled_safe")
def scheduled_safe():
    ensure_safe_schedule_db()
    con = db()
    rows = con.execute("""
        SELECT s.*, c.title, c.username, c.role
        FROM telegram_safe_scheduled_messages s
        LEFT JOIN telegram_chats c ON c.chat_id=s.target_chat_id
        ORDER BY s.id DESC
        LIMIT 200
    """).fetchall()
    con.close()
    return {"ok": True, "items": [dict(r) for r in rows]}


def run_safe_scheduled_once():
    ensure_safe_schedule_db()
    now = datetime.utcnow().isoformat(timespec="seconds")

    con = db()
    rows = con.execute("""
        SELECT *
        FROM telegram_safe_scheduled_messages
        WHERE status='scheduled'
          AND scheduled_at <= ?
        ORDER BY scheduled_at ASC
        LIMIT 20
    """, (now,)).fetchall()
    con.close()

    sent = []

    for row in rows:
        # ============================================================
        # PLANNER REMINDER FILTER V1
        # ============================================================

        if row["purpose"] == "planner_reminder":
            result = send_safe({
                "purpose": "planner_internal",
                "text": row["text"],
            })

        else:
            result = send_safe({
                "purpose": row["purpose"],
                "target_chat_id": row["target_chat_id"],
                "text": row["text"],
            })

        ok = bool(result.get("ok"))

        con = db()
        con.execute("""
            UPDATE telegram_safe_scheduled_messages
            SET status=?,
                sent_at=?,
                error=?
            WHERE id=?
        """, (
            "sent" if ok else "failed",
            datetime.utcnow().isoformat(timespec="seconds") if ok else None,
            None if ok else str(result),
            row["id"],
        ))
        con.commit()
        con.close()

        sent.append({"id": row["id"], "ok": ok, "result": result})

    return {"ok": True, "processed": len(sent), "items": sent}


@router.post("/run_scheduled_safe_once")
def run_scheduled_safe_once():
    return run_safe_scheduled_once()


def start_safe_scheduler_loop():
    def loop():
        while True:
            try:
                run_safe_scheduled_once()
            except Exception as e:
                print("[telegram safe scheduler error]", e)
            time.sleep(30)

    th = threading.Thread(target=loop, daemon=True)
    th.start()


try:
    ensure_safe_schedule_db()
    start_safe_scheduler_loop()
except Exception as e:
    print("[telegram safe scheduler init error]", e)

# ============================================================================
# /TELEGRAM TARGET AI + SCHEDULER V1
# ============================================================================

# ============================================================================
# STRICT CLIENT TARGET SEND FINAL
# ============================================================================

@router.post("/send_client_target")
def send_client_target(payload: dict = Body(default={})):
    print("[SEND_CLIENT_TARGET PAYLOAD]", payload)

    text = str(payload.get("text") or payload.get("message") or "").strip()
    raw_target_chat_id = str(payload.get("target_chat_id") or payload.get("chat_id") or "").strip()
    target_chat_id = raw_target_chat_id
    thread_id = None

    if ":" in raw_target_chat_id:
        target_chat_id, thread_id = raw_target_chat_id.split(":", 1)

    if not text:
        return {"ok": False, "error": "empty_text"}

    if not target_chat_id:
        return {"ok": False, "error": "target_chat_required"}

    con = db()
    row = con.execute(
        """
        SELECT chat_id, role, enabled
        FROM telegram_chats
        WHERE chat_id=?
        LIMIT 1
        """,
        (target_chat_id,),
    ).fetchone()
    con.close()

    if not row:
        return {"ok": False, "error": "target_chat_not_found", "chat_id": target_chat_id}

    if int(row["enabled"] or 0) != 1:
        return {"ok": False, "error": "target_chat_disabled", "chat_id": target_chat_id}

    if row["role"] not in ("client_group", "client_channel"):
        return {
            "ok": False,
            "error": "not_client_target",
            "chat_id": target_chat_id,
            "role": row["role"],
        }

    tg = send_to_chat(target_chat_id, text, purpose="client_funnel", thread_id=thread_id)

    return {
        "ok": bool(tg.get("ok")),
        "purpose": "client_funnel",
        "target_chat_id": target_chat_id,
        "sent_count": 1 if tg.get("ok") else 0,
        "results": [{
            "chat_id": target_chat_id,
            "ok": bool(tg.get("ok")),
            "telegram": tg,
        }],
    }

# ============================================================================
# /STRICT CLIENT TARGET SEND FINAL
# ============================================================================
