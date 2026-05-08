
from typing import Optional, Dict, Any
from fastapi import APIRouter
from pydantic import BaseModel

from funnel_core import (
    init_funnel_db,
    create_default_funnel,
    list_funnels,
    get_funnel,
    process_funnel_event,
    run_due_jobs,
    funnel_stats,
    update_funnel,
    upsert_funnel_step,
    delete_funnel_step,
    run_contact_next_step,
    funnel_contact_debug,
    list_telegram_destinations,
    bind_contact_telegram_chat,
    send_telegram_message,
    build_telegram_start_link,
    handle_telegram_start_update,
)

router = APIRouter(prefix="/api/funnels", tags=["funnels"])

class FunnelCreateRequest(BaseModel):
    name: Optional[str] = None



class FunnelUpdateRequest(BaseModel):
    name: Optional[str] = None
    status: Optional[str] = None
    source_platform: Optional[str] = None
    source_type: Optional[str] = None
    goal: Optional[str] = None
    trigger_type: Optional[str] = None
    trigger_value: Optional[str] = None
    output_type: Optional[str] = None
    output_target: Optional[str] = None
    ai_enabled: Optional[int] = None
    config: Optional[Dict[str, Any]] = None

class FunnelStepUpsertRequest(BaseModel):
    funnel_id: int
    step_order: int
    step_type: str
    step_name: Optional[str] = ""
    config: Optional[Dict[str, Any]] = None

class FunnelStepDeleteRequest(BaseModel):
    funnel_id: int
    step_order: int



class FunnelBindTelegramRequest(BaseModel):
    funnel_id: int
    platform: str = "instagram"
    external_user_id: str
    telegram_chat_id: str
    username: Optional[str] = ""



class FunnelTelegramStartLinkRequest(BaseModel):
    funnel_id: int
    external_user_id: str
    bot_username: Optional[str] = None

class FunnelTelegramUpdateRequest(BaseModel):
    update: Dict[str, Any]

class FunnelTelegramSendTestRequest(BaseModel):
    chat_id: str
    text: str

class FunnelRunNextRequest(BaseModel):
    funnel_id: int
    platform: str = "instagram"
    external_user_id: str

class FunnelEventRequest(BaseModel):
    funnel_id: int
    platform: str = "instagram"
    external_user_id: str
    username: Optional[str] = ""
    event_type: str = "manual"
    payload: Optional[Dict[str, Any]] = None

@router.get("/health")
def funnels_health():
    init_funnel_db()
    return {"ok": True, "module": "funnels", "status": "ready"}

@router.post("/init")
def funnels_init():
    init_funnel_db()
    return {"ok": True}

@router.post("/default")
def funnels_create_default(req: FunnelCreateRequest = FunnelCreateRequest()):
    funnel_id = create_default_funnel(req.name or "Instagram → Telegram → Consultation")
    return {"ok": True, "funnel_id": funnel_id, "funnel": get_funnel(funnel_id)}

@router.get("")
def funnels_list():
    return {"ok": True, "items": list_funnels()}


# === DYNAMIC KEY FUNNELS RUNTIME V1 ===
import os
import sqlite3
import json
import re
from datetime import datetime
from urllib.parse import quote
from pathlib import Path

CONTENT_DB_PATH = os.getenv(
    "CONTENT_AI_DB_PATH",
    os.getenv("CONTENT_AI_DB", os.path.join(os.getcwd(), "data", "content.db"))
)

IG_WEBHOOK_DB_PATH = os.getenv(
    "IG_WEBHOOK_DB_PATH",
    os.path.join(os.getcwd(), "db", "instagram.sqlite")
)

def dyn_now():
    return datetime.now().isoformat(timespec="seconds")

def dyn_slug(x: str, max_len: int = 60):
    x = str(x or "").strip().lower()
    x = re.sub(r"[^a-z0-9а-яіїєґ_]+", "_", x, flags=re.IGNORECASE)
    x = x.strip("_")
    return (x[:max_len] or "")

def dyn_json(x):
    return json.dumps(x or {}, ensure_ascii=False)

def dyn_con():
    Path(CONTENT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(CONTENT_DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def dyn_render(tpl: str, ctx: dict):
    out = str(tpl or "")
    for k, v in (ctx or {}).items():
        out = out.replace("{{" + str(k) + "}}", str(v or ""))
    return out

def dyn_bot_username(cfg_value=""):
    return (
        str(cfg_value or "").strip().lstrip("@")
        or os.getenv("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
        or os.getenv("TG_BOT_USERNAME", "").strip().lstrip("@")
        or os.getenv("BOT_USERNAME", "").strip().lstrip("@")
    )

def dyn_init():
    con = dyn_con()
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS funnel_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            updated_at TEXT,
            funnel_key TEXT UNIQUE NOT NULL,
            funnel_name TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 100,
            source_platform TEXT DEFAULT 'instagram',
            trigger_keywords TEXT DEFAULT '',
            content_keywords TEXT DEFAULT '',
            telegram_bot_username TEXT DEFAULT '',
            telegram_channel_url TEXT DEFAULT '',
            target_url TEXT DEFAULT '',
            next_funnel_key TEXT DEFAULT '',
            dm_template TEXT DEFAULT '',
            start_payload_template TEXT DEFAULT '',
            intro_text TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            settings_json TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS funnel_steps_dynamic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            updated_at TEXT,
            funnel_key TEXT NOT NULL,
            step_key TEXT NOT NULL,
            step_order INTEGER DEFAULT 100,
            active INTEGER DEFAULT 1,
            trigger_stage TEXT DEFAULT '',
            next_stage TEXT DEFAULT '',
            message_text TEXT DEFAULT '',
            button_text TEXT DEFAULT '',
            button_url TEXT DEFAULT '',
            delay_minutes INTEGER DEFAULT 0,
            settings_json TEXT DEFAULT '',
            UNIQUE(funnel_key, step_key)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS funnel_sessions_dynamic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            source_platform TEXT DEFAULT 'instagram',
            source_user_id TEXT DEFAULT '',
            source_username TEXT DEFAULT '',
            source_message TEXT DEFAULT '',
            source_webhook_message_id INTEGER DEFAULT 0,
            funnel_key TEXT NOT NULL,
            funnel_name TEXT DEFAULT '',
            status TEXT DEFAULT 'created',
            stage TEXT DEFAULT 'created',
            telegram_chat_id TEXT DEFAULT '',
            telegram_username TEXT DEFAULT '',
            telegram_start_payload TEXT DEFAULT '',
            telegram_deeplink TEXT DEFAULT '',
            dm_text TEXT DEFAULT '',
            started_by TEXT DEFAULT 'manual',
            mode TEXT DEFAULT 'draft',
            sent_at TEXT DEFAULT '',
            error TEXT DEFAULT '',
            raw_json TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS ix_funnel_sessions_dynamic_lookup
        ON funnel_sessions_dynamic(source_platform, source_user_id, funnel_key, status)
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS ix_funnel_sessions_dynamic_payload
        ON funnel_sessions_dynamic(telegram_start_payload)
    """)

    con.commit()
    con.close()

def dyn_get_config(funnel_key: str):
    dyn_init()
    key = dyn_slug(funnel_key)
    con = dyn_con()
    row = con.execute("SELECT * FROM funnel_configs WHERE funnel_key=? LIMIT 1", (key,)).fetchone()
    con.close()
    return dict(row) if row else None

def dyn_steps(funnel_key: str):
    dyn_init()
    key = dyn_slug(funnel_key)
    con = dyn_con()
    rows = con.execute("""
        SELECT *
        FROM funnel_steps_dynamic
        WHERE funnel_key=?
        ORDER BY step_order ASC, id ASC
    """, (key,)).fetchall()
    con.close()
    return [dict(r) for r in rows]

def dyn_start_payload(cfg: dict, source_user_id: str):
    tpl = str(cfg.get("start_payload_template") or "").strip()
    ctx = {
        "funnel_key": cfg.get("funnel_key") or "",
        "source_user_id": source_user_id,
        "ig_user_id": source_user_id,
    }
    raw = dyn_render(tpl, ctx) if tpl else f"funnel_{ctx['funnel_key']}__ig_{source_user_id}"
    raw = re.sub(r"[^A-Za-z0-9_]+", "_", raw).strip("_")
    return raw[:64]

def dyn_deeplink(cfg: dict, start_payload: str):
    bot = dyn_bot_username(cfg.get("telegram_bot_username") or "")
    if not bot:
        return ""
    return f"https://t.me/{bot}?start={quote(start_payload)}"

def dyn_default_dm_template():
    return (
        "🌿 Я підготувала для тебе матеріал «{{funnel_name}}».\\n\\n"
        "👇 Натисни й почни тут:\\n{{telegram_deeplink}}"
    )

def dyn_bridge_to_ig_plan(payload: dict):
    """
    Паралельно синхронізує funnel_configs у стару таблицю ig_reaction_funnel_plans,
    щоб існуючий Instagram AI matcher міг вибирати selected_funnel_plan_key.
    """
    con = dyn_con()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS ig_reaction_funnel_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT,
            updated_at TEXT,
            plan_key TEXT UNIQUE,
            plan_name TEXT DEFAULT '',
            active INTEGER DEFAULT 1,
            priority INTEGER DEFAULT 100,
            trigger_keywords TEXT DEFAULT '',
            content_keywords TEXT DEFAULT '',
            plan_goal TEXT DEFAULT '',
            public_cta TEXT DEFAULT '',
            direct_cta TEXT DEFAULT '',
            followup_sequence TEXT DEFAULT '',
            notes TEXT DEFAULT ''
        )
    """)

    now = dyn_now()
    key = dyn_slug(payload.get("funnel_key") or "")
    cur.execute("""
        INSERT INTO ig_reaction_funnel_plans (
            created_at, updated_at, plan_key, plan_name, active, priority,
            trigger_keywords, content_keywords, plan_goal, public_cta, direct_cta,
            followup_sequence, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(plan_key) DO UPDATE SET
            updated_at=excluded.updated_at,
            plan_name=excluded.plan_name,
            active=excluded.active,
            priority=excluded.priority,
            trigger_keywords=excluded.trigger_keywords,
            content_keywords=excluded.content_keywords,
            plan_goal=excluded.plan_goal,
            public_cta=excluded.public_cta,
            direct_cta=excluded.direct_cta,
            followup_sequence=excluded.followup_sequence,
            notes=excluded.notes
    """, (
        now, now, key,
        str(payload.get("funnel_name") or payload.get("plan_name") or key),
        int(payload.get("active", 1)),
        int(payload.get("priority", 100)),
        str(payload.get("trigger_keywords") or ""),
        str(payload.get("content_keywords") or ""),
        str(payload.get("plan_goal") or payload.get("notes") or ""),
        str(payload.get("public_cta") or ""),
        str(payload.get("direct_cta") or ""),
        str(payload.get("followup_sequence") or ""),
        str(payload.get("notes") or ""),
    ))
    con.commit()
    con.close()

@router.get("/runtime/status")
def dyn_runtime_status():
    dyn_init()
    con = dyn_con()
    cur = con.cursor()
    tables = {}
    for t in ["funnel_configs", "funnel_steps_dynamic", "funnel_sessions_dynamic", "ig_reaction_funnel_plans"]:
        try:
            tables[t] = cur.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        except Exception:
            tables[t] = None
    con.close()
    return {
        "ok": True,
        "status": "ok",
        "content_db": CONTENT_DB_PATH,
        "ig_webhook_db": IG_WEBHOOK_DB_PATH,
        "telegram_bot_username_exists": bool(dyn_bot_username()),
        "tables": tables,
    }

@router.post("/configs/upsert")
def dyn_config_upsert(payload: Dict[str, Any]):
    dyn_init()
    key = dyn_slug(payload.get("funnel_key") or payload.get("plan_key") or "")
    if not key:
        return {"ok": False, "status": "error", "error": "funnel_key required"}

    now = dyn_now()
    con = dyn_con()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO funnel_configs (
            created_at, updated_at, funnel_key, funnel_name, active, priority,
            source_platform, trigger_keywords, content_keywords,
            telegram_bot_username, telegram_channel_url, target_url, next_funnel_key,
            dm_template, start_payload_template, intro_text, notes, settings_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(funnel_key) DO UPDATE SET
            updated_at=excluded.updated_at,
            funnel_name=excluded.funnel_name,
            active=excluded.active,
            priority=excluded.priority,
            source_platform=excluded.source_platform,
            trigger_keywords=excluded.trigger_keywords,
            content_keywords=excluded.content_keywords,
            telegram_bot_username=excluded.telegram_bot_username,
            telegram_channel_url=excluded.telegram_channel_url,
            target_url=excluded.target_url,
            next_funnel_key=excluded.next_funnel_key,
            dm_template=excluded.dm_template,
            start_payload_template=excluded.start_payload_template,
            intro_text=excluded.intro_text,
            notes=excluded.notes,
            settings_json=excluded.settings_json
    """, (
        now, now, key,
        str(payload.get("funnel_name") or payload.get("plan_name") or key),
        int(payload.get("active", 1)),
        int(payload.get("priority", 100)),
        str(payload.get("source_platform") or "instagram"),
        str(payload.get("trigger_keywords") or ""),
        str(payload.get("content_keywords") or ""),
        str(payload.get("telegram_bot_username") or ""),
        str(payload.get("telegram_channel_url") or ""),
        str(payload.get("target_url") or ""),
        dyn_slug(payload.get("next_funnel_key") or ""),
        str(payload.get("dm_template") or ""),
        str(payload.get("start_payload_template") or ""),
        str(payload.get("intro_text") or ""),
        str(payload.get("notes") or ""),
        dyn_json(payload.get("settings") or payload.get("settings_json") or {}),
    ))

    con.commit()
    con.close()

    if str(payload.get("source_platform") or "instagram").lower() == "instagram":
        dyn_bridge_to_ig_plan({**payload, "funnel_key": key})

    return {"ok": True, "status": "ok", "item": dyn_get_config(key)}

@router.get("/configs/list")
def dyn_configs_list(active_only: int = 0):
    dyn_init()
    con = dyn_con()
    if int(active_only or 0):
        rows = con.execute("""
            SELECT *
            FROM funnel_configs
            WHERE active=1
            ORDER BY priority ASC, id DESC
        """).fetchall()
    else:
        rows = con.execute("""
            SELECT *
            FROM funnel_configs
            ORDER BY priority ASC, id DESC
        """).fetchall()
    con.close()
    return {"ok": True, "status": "ok", "items": [dict(r) for r in rows]}

@router.get("/configs/by-key/{funnel_key}")
def dyn_config_get(funnel_key: str):
    cfg = dyn_get_config(funnel_key)
    if not cfg:
        return {"ok": False, "status": "error", "error": "not_found", "funnel_key": funnel_key}
    return {"ok": True, "status": "ok", "item": cfg, "steps": dyn_steps(funnel_key)}

@router.post("/configs/{funnel_key}/steps/upsert")
def dyn_step_upsert(funnel_key: str, payload: Dict[str, Any]):
    dyn_init()
    key = dyn_slug(funnel_key)
    if not dyn_get_config(key):
        return {"ok": False, "status": "error", "error": "funnel config not found", "funnel_key": key}

    step_key = dyn_slug(payload.get("step_key") or "")
    if not step_key:
        return {"ok": False, "status": "error", "error": "step_key required"}

    now = dyn_now()
    con = dyn_con()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO funnel_steps_dynamic (
            created_at, updated_at, funnel_key, step_key, step_order, active,
            trigger_stage, next_stage, message_text, button_text, button_url,
            delay_minutes, settings_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(funnel_key, step_key) DO UPDATE SET
            updated_at=excluded.updated_at,
            step_order=excluded.step_order,
            active=excluded.active,
            trigger_stage=excluded.trigger_stage,
            next_stage=excluded.next_stage,
            message_text=excluded.message_text,
            button_text=excluded.button_text,
            button_url=excluded.button_url,
            delay_minutes=excluded.delay_minutes,
            settings_json=excluded.settings_json
    """, (
        now, now, key, step_key,
        int(payload.get("step_order", 100)),
        int(payload.get("active", 1)),
        str(payload.get("trigger_stage") or ""),
        str(payload.get("next_stage") or ""),
        str(payload.get("message_text") or ""),
        str(payload.get("button_text") or ""),
        str(payload.get("button_url") or ""),
        int(payload.get("delay_minutes", 0)),
        dyn_json(payload.get("settings") or payload.get("settings_json") or {}),
    ))

    con.commit()
    con.close()

    return {"ok": True, "status": "ok", "items": dyn_steps(key)}

@router.post("/configs/{funnel_key}/steps/delete")
def dyn_step_delete(funnel_key: str, payload: Dict[str, Any]):
    key = dyn_slug(funnel_key)
    step_key = dyn_slug(payload.get("step_key") or "")
    if not step_key:
        return {"ok": False, "status": "error", "error": "step_key required"}

    con = dyn_con()
    cur = con.cursor()
    cur.execute("DELETE FROM funnel_steps_dynamic WHERE funnel_key=? AND step_key=?", (key, step_key))
    changed = cur.rowcount
    con.commit()
    con.close()
    return {"ok": True, "status": "ok", "deleted": changed, "items": dyn_steps(key)}

@router.get("/runtime/leads")
def dyn_runtime_leads(limit: int = 100):
    dyn_init()
    limit = max(1, min(int(limit or 100), 500))
    items = []

    con = dyn_con()
    con.row_factory = sqlite3.Row

    try:
        rows = con.execute("""
            SELECT
                id,
                created_at,
                platform AS source_platform,
                external_user_id AS source_user_id,
                username,
                reaction_text AS text,
                matched_plan_key,
                matched_plan_name,
                status
            FROM ig_reactions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        for r in rows:
            d = dict(r)
            d["source_table"] = "ig_reactions"
            items.append(d)
    except Exception:
        pass

    try:
        rows = con.execute("""
            SELECT
                id,
                created_at,
                external_user_id AS source_user_id,
                username,
                direct_reply AS text,
                selected_funnel_plan_key AS matched_plan_key,
                selected_funnel_plan_name AS matched_plan_name,
                status
            FROM ig_ai_reply_drafts
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        for r in rows:
            d = dict(r)
            d["source_platform"] = "instagram"
            d["source_table"] = "ig_ai_reply_drafts"
            items.append(d)
    except Exception:
        pass

    con.close()

    if Path(IG_WEBHOOK_DB_PATH).exists() and Path(IG_WEBHOOK_DB_PATH).stat().st_size > 0:
        try:
            con2 = sqlite3.connect(IG_WEBHOOK_DB_PATH)
            con2.row_factory = sqlite3.Row
            rows = con2.execute("""
                SELECT
                    id,
                    created_at,
                    sender_id AS source_user_id,
                    text,
                    'instagram' AS source_platform
                FROM instagram_webhook_messages
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()

            for r in rows:
                d = dict(r)
                d["source_table"] = "instagram_webhook_messages"
                d["matched_plan_key"] = ""
                d["matched_plan_name"] = ""
                items.append(d)

            con2.close()
        except Exception:
            pass

    items = sorted(items, key=lambda x: str(x.get("created_at") or ""), reverse=True)[:limit]
    return {"ok": True, "status": "ok", "items": items}

@router.post("/runtime/manual-start")
def dyn_runtime_manual_start(payload: Dict[str, Any]):
    dyn_init()

    funnel_key = dyn_slug(payload.get("funnel_key") or payload.get("selected_funnel_plan_key") or "")
    if not funnel_key:
        return {"ok": False, "status": "error", "error": "funnel_key required"}

    cfg = dyn_get_config(funnel_key)
    if not cfg:
        return {"ok": False, "status": "error", "error": "funnel config not found", "funnel_key": funnel_key}

    source_platform = str(payload.get("source_platform") or cfg.get("source_platform") or "instagram").strip().lower()
    source_user_id = str(payload.get("source_user_id") or payload.get("external_user_id") or "").strip()
    source_username = str(payload.get("source_username") or payload.get("username") or "").strip()
    source_message = str(payload.get("source_message") or payload.get("text") or "").strip()
    mode = str(payload.get("mode") or "draft").strip().lower()
    if mode not in ("draft", "send"):
        mode = "draft"

    if not source_user_id:
        return {"ok": False, "status": "error", "error": "source_user_id required"}

    start_payload = dyn_start_payload(cfg, source_user_id)
    deeplink = dyn_deeplink(cfg, start_payload)
    if not deeplink:
        return {
            "ok": False,
            "status": "error",
            "error": "telegram bot username missing",
            "hint": "Set telegram_bot_username in funnel config or TELEGRAM_BOT_USERNAME env",
        }

    ctx = {
        "funnel_key": funnel_key,
        "funnel_name": cfg.get("funnel_name") or funnel_key,
        "source_user_id": source_user_id,
        "source_message": source_message,
        "telegram_deeplink": deeplink,
        "telegram_channel_url": cfg.get("telegram_channel_url") or "",
        "target_url": cfg.get("target_url") or "",
    }

    dm_tpl = str(cfg.get("dm_template") or "").strip() or dyn_default_dm_template()
    dm_text = dyn_render(str(payload.get("dm_text") or "").strip() or dm_tpl, ctx)

    now = dyn_now()
    con = dyn_con()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO funnel_sessions_dynamic (
            created_at, updated_at, source_platform, source_user_id, source_username,
            source_message, source_webhook_message_id, funnel_key, funnel_name,
            status, stage, telegram_start_payload, telegram_deeplink,
            dm_text, started_by, mode, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now, now, source_platform, source_user_id, source_username,
        source_message, int(payload.get("source_webhook_message_id") or 0),
        funnel_key, cfg.get("funnel_name") or funnel_key,
        "created" if mode == "draft" else "send_pending_manual",
        "manual_created",
        start_payload, deeplink,
        dm_text, "manual", mode, dyn_json(payload),
    ))

    session_id = cur.lastrowid
    con.commit()
    con.close()

    return {
        "ok": True,
        "status": "ok",
        "session_id": session_id,
        "funnel_key": funnel_key,
        "telegram_start_payload": start_payload,
        "telegram_deeplink": deeplink,
        "dm_text": dm_text,
        "mode": mode,
    }

@router.get("/runtime/sessions")
def dyn_runtime_sessions(limit: int = 100):
    dyn_init()
    limit = max(1, min(int(limit or 100), 500))
    con = dyn_con()
    rows = con.execute("""
        SELECT *
        FROM funnel_sessions_dynamic
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    con.close()
    return {"ok": True, "status": "ok", "items": [dict(r) for r in rows]}

@router.post("/runtime/session/{session_id}/stage")
def dyn_runtime_stage(session_id: int, payload: Dict[str, Any]):
    dyn_init()
    stage = str(payload.get("stage") or "").strip()
    status = str(payload.get("status") or "").strip()
    if not stage:
        return {"ok": False, "status": "error", "error": "stage required"}

    con = dyn_con()
    cur = con.cursor()
    cur.execute("""
        UPDATE funnel_sessions_dynamic
        SET stage=?,
            status=CASE WHEN ? != '' THEN ? ELSE status END,
            updated_at=?
        WHERE id=?
    """, (stage, status, status, dyn_now(), int(session_id)))
    changed = cur.rowcount
    con.commit()
    con.close()
    return {"ok": True, "status": "ok", "updated": changed}

# === /DYNAMIC KEY FUNNELS RUNTIME V1 ===



@router.get("/{funnel_id}")
def funnels_get(funnel_id: int):
    f = get_funnel(funnel_id)
    return {"ok": bool(f), "item": f}

@router.post("/event")
def funnels_event(req: FunnelEventRequest):
    res = process_funnel_event(
        funnel_id=req.funnel_id,
        platform=req.platform,
        external_user_id=req.external_user_id,
        username=req.username or "",
        event_type=req.event_type,
        payload=req.payload or {},
    )
    return res

@router.post("/jobs/run-due")
def funnels_run_jobs():
    return {"ok": True, "items": run_due_jobs()}

@router.get("/analytics/summary")
def funnels_analytics_summary():
    return {"ok": True, "items": funnel_stats()}


@router.patch("/{funnel_id}")
def funnels_update(funnel_id: int, req: FunnelUpdateRequest):
    patch = {k: v for k, v in req.dict().items() if v is not None}
    return {"ok": True, "item": update_funnel(funnel_id, patch)}

@router.post("/steps/upsert")
def funnels_step_upsert(req: FunnelStepUpsertRequest):
    item = upsert_funnel_step(
        funnel_id=req.funnel_id,
        step_order=req.step_order,
        step_type=req.step_type,
        step_name=req.step_name or "",
        config=req.config or {},
    )
    return {"ok": True, "item": item}

@router.post("/steps/delete")
def funnels_step_delete(req: FunnelStepDeleteRequest):
    item = delete_funnel_step(req.funnel_id, req.step_order)
    return {"ok": True, "item": item}

@router.post("/contact/run-next")
def funnels_contact_run_next(req: FunnelRunNextRequest):
    return run_contact_next_step(req.funnel_id, req.platform, req.external_user_id)

@router.get("/contact/debug")
def funnels_contact_debug_endpoint(funnel_id: int, platform: str, external_user_id: str):
    return funnel_contact_debug(funnel_id, platform, external_user_id)

@router.get("/telegram/destinations")
def funnels_telegram_destinations():
    return list_telegram_destinations()


@router.post("/contact/bind-telegram")
def funnels_contact_bind_telegram(req: FunnelBindTelegramRequest):
    contact = bind_contact_telegram_chat(
        funnel_id=req.funnel_id,
        platform=req.platform,
        external_user_id=req.external_user_id,
        telegram_chat_id=req.telegram_chat_id,
        username=req.username or "",
    )
    return {"ok": True, "contact": contact}

@router.post("/telegram/send-test")
def funnels_telegram_send_test(req: FunnelTelegramSendTestRequest):
    return send_telegram_message(req.chat_id, req.text)


@router.post("/telegram/start-link")
def funnels_telegram_start_link(req: FunnelTelegramStartLinkRequest):
    return {
        "ok": True,
        "url": build_telegram_start_link(req.bot_username, req.funnel_id, req.external_user_id)
    }

@router.post("/telegram/handle-start")
def funnels_telegram_handle_start(req: FunnelTelegramUpdateRequest):
    return handle_telegram_start_update(req.update)


@router.post("/telegram/webhook")
def funnels_telegram_webhook(update: Dict[str, Any]):
    """
    Telegram webhook endpoint for funnel /start payloads.
    Only handles: /start funnel_<id>__<external_user_id>
    Other messages are safely ignored.
    """
    try:
        text = (
            ((update.get("message") or {}).get("text"))
            or ((update.get("edited_message") or {}).get("text"))
            or ""
        )

        if not text.startswith("/start funnel_"):
            return {
                "ok": True,
                "skipped": True,
                "reason": "not_funnel_start"
            }

        return handle_telegram_start_update(update)

    except Exception as e:
        return {
            "ok": False,
            "error": str(e)
        }
