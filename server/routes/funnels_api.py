
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
    lead_count_after = None

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






# === FUNNEL BACKUP RESTORE V2 ===
def _table_exists(con, table):
    try:
        row = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,)
        ).fetchone()
        return bool(row)
    except Exception:
        return False

def _dump_table(con, table, order_by="id ASC"):
    if not _table_exists(con, table):
        return []
    try:
        rows = con.execute(f"SELECT * FROM {table} ORDER BY {order_by}").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        rows = con.execute(f"SELECT * FROM {table}").fetchall()
        return [dict(r) for r in rows]

def _table_columns(con, table):
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []

def _insert_or_replace_rows(con, table, rows, preserve_id=True):
    if not rows:
        return 0

    if not _table_exists(con, table):
        return 0

    cols_existing = _table_columns(con, table)
    imported = 0

    for row in rows:
        if not isinstance(row, dict):
            continue

        clean = {}
        for k, v in row.items():
            if k in cols_existing:
                clean[k] = v

        if not clean:
            continue

        if not preserve_id and "id" in clean:
            clean.pop("id", None)

        cols = list(clean.keys())
        placeholders = ",".join(["?"] * len(cols))
        col_sql = ",".join(cols)

        if "id" in clean:
            sql = f"INSERT OR REPLACE INTO {table} ({col_sql}) VALUES ({placeholders})"
        else:
            sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"

        con.execute(sql, [clean[c] for c in cols])
        imported += 1

    return imported

@router.get("/backup/export")
def funnels_backup_export_full():
    dyn_init()

    con = dyn_con()
    con.row_factory = sqlite3.Row

    content_tables = {
        "funnel_configs": _dump_table(con, "funnel_configs", "priority ASC, id ASC"),
        "funnel_steps_dynamic": _dump_table(con, "funnel_steps_dynamic", "funnel_key ASC, step_order ASC, id ASC"),
        "funnel_sessions_dynamic": _dump_table(con, "funnel_sessions_dynamic", "id ASC"),
        "ig_reaction_funnel_plans": _dump_table(con, "ig_reaction_funnel_plans", "priority ASC, id ASC"),
        "ig_reactions": _dump_table(con, "ig_reactions", "id ASC"),
        "ig_ai_reply_drafts": _dump_table(con, "ig_ai_reply_drafts", "id ASC"),
    }

    con.close()

    ig_webhook_rows = []
    try:
        if Path(IG_WEBHOOK_DB_PATH).exists():
            con_ig = sqlite3.connect(IG_WEBHOOK_DB_PATH)
            con_ig.row_factory = sqlite3.Row
            ig_webhook_rows = _dump_table(con_ig, "instagram_webhook_messages", "id ASC")
            con_ig.close()
    except Exception as e:
        ig_webhook_rows = [{"_backup_error": str(e)}]

    return {
        "ok": True,
        "status": "ok",
        "backup_type": "funnels_full_v2",
        "exported_at": dyn_now(),
        "content_db": CONTENT_DB_PATH,
        "ig_webhook_db": IG_WEBHOOK_DB_PATH,
        "tables": {
            **content_tables,
            "instagram_webhook_messages": ig_webhook_rows,
        },
        "telegram_db": _dump_sqlite_db_generic(TELEGRAM_DB_PATH),
        "telegram_bundle": build_telegram_backup_bundle(),
        "counts": {
            **{k: len(v) for k, v in content_tables.items()},
            "instagram_webhook_messages": len(ig_webhook_rows),
        }
    }

@router.post("/backup/import")
def funnels_backup_import_full(payload: Dict[str, Any]):
    try:
        dyn_init()
    
        backup_type = payload.get("backup_type")
        if backup_type not in ("funnels_full_v2", "funnels_dynamic_v1"):
            return {
                "ok": False,
                "status": "error",
                "error": "invalid backup_type",
                "expected": "funnels_full_v2",
            }
    
        # Backward compatibility with old format
        if backup_type == "funnels_dynamic_v1":
            tables = {
                "funnel_configs": payload.get("funnels") or [],
                "funnel_steps_dynamic": payload.get("steps") or [],
            }
        else:
            tables = payload.get("tables") or {}
    
        con = dyn_con()
        con.row_factory = sqlite3.Row
    
        imported = {}
    
        import_order = [
            "funnel_configs",
            "funnel_steps_dynamic",
            "funnel_sessions_dynamic",
            "funnel_events",
            "funnel_contacts",
            "funnel_jobs",
            "funnel_leads",
            "ig_reaction_funnel_plans",
            "ig_reactions",
            "ig_ai_reply_drafts",
        ]
    
        for table in import_order:
            rows = tables.get(table) or []
            imported[table] = _insert_or_replace_rows(con, table, rows, preserve_id=True)
    
        con.commit()
        con.close()
    
        # Restore IG webhook DB separately
        imported_ig_webhook = 0
        ig_rows = tables.get("instagram_webhook_messages") or []
        if ig_rows:
            try:
                Path(IG_WEBHOOK_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
                con_ig = sqlite3.connect(IG_WEBHOOK_DB_PATH)
                con_ig.row_factory = sqlite3.Row
    
                con_ig.execute("""
                    CREATE TABLE IF NOT EXISTS instagram_webhook_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        object TEXT,
                        entry_id TEXT,
                        event_time INTEGER,
                        sender_id TEXT,
                        recipient_id TEXT,
                        timestamp INTEGER,
                        mid TEXT UNIQUE,
                        text TEXT,
                        raw_json TEXT
                    )
                """)
    
                imported_ig_webhook = _insert_or_replace_rows(
                    con_ig,
                    "instagram_webhook_messages",
                    ig_rows,
                    preserve_id=True
                )
    
                con_ig.commit()
                con_ig.close()
            except Exception as e:
                imported["instagram_webhook_messages_error"] = str(e)
    
        imported["instagram_webhook_messages"] = imported_ig_webhook
    
        if backup_type == "funnels_full_v2" and payload.get("telegram_bundle"):
            imported["telegram_bundle"] = restore_telegram_backup_bundle(payload.get("telegram_bundle"))
    
        if backup_type == "funnels_full_v2" and payload.get("telegram_db"):
            imported["telegram_db"] = _restore_sqlite_db_generic(
                TELEGRAM_DB_PATH,
                payload.get("telegram_db")
            )
    
        return {
            "ok": True,
            "status": "ok",
            "backup_type": backup_type,
            "imported": imported,
        }
    except Exception as e:
        return {"ok": False, "status": "error", "where": "backup_import", "error": repr(e)}

@router.get("/backup/counts")
def funnels_backup_counts():
    dyn_init()

    con = dyn_con()
    con.row_factory = sqlite3.Row

    tables = [
        "funnel_configs",
        "funnel_steps_dynamic",
        "funnel_sessions_dynamic",
        "ig_reaction_funnel_plans",
        "ig_reactions",
        "ig_ai_reply_drafts",
    ]

    counts = {}
    for t in tables:
        try:
            counts[t] = con.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
        except Exception:
            counts[t] = None

    con.close()

    try:
        if Path(IG_WEBHOOK_DB_PATH).exists():
            con_ig = sqlite3.connect(IG_WEBHOOK_DB_PATH)
            counts["instagram_webhook_messages"] = con_ig.execute(
                "SELECT COUNT(*) AS n FROM instagram_webhook_messages"
            ).fetchone()[0]
            con_ig.close()
        else:
            counts["instagram_webhook_messages"] = 0
    except Exception:
        counts["instagram_webhook_messages"] = None

    return {
        "ok": True,
        "status": "ok",
        "counts": counts,
        "content_db": CONTENT_DB_PATH,
        "ig_webhook_db": IG_WEBHOOK_DB_PATH,
    }

# === /FUNNEL BACKUP RESTORE V2 ===





# === FUNNEL LEAD INBOX V1 ===
def funnel_leads_init():
    dyn_init()
    con = dyn_con()
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS funnel_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,

            source_platform TEXT DEFAULT 'instagram',
            source_table TEXT DEFAULT '',
            source_row_id INTEGER DEFAULT 0,

            external_user_id TEXT DEFAULT '',
            username TEXT DEFAULT '',
            text TEXT DEFAULT '',

            matched_funnel_key TEXT DEFAULT '',
            matched_funnel_name TEXT DEFAULT '',
            status TEXT DEFAULT 'new',

            raw_json TEXT DEFAULT '',

            UNIQUE(source_platform, source_table, source_row_id)
        )
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS ix_funnel_leads_user
        ON funnel_leads(source_platform, external_user_id)
    """)
    cur.execute("""
        CREATE INDEX IF NOT EXISTS ix_funnel_leads_status
        ON funnel_leads(status, created_at)
    """)
    con.commit()
    con.close()

def funnel_leads_match_funnel(text: str):
    text_norm = str(text or "").lower().strip()
    con = dyn_con()
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT *
        FROM funnel_configs
        WHERE active=1
        ORDER BY priority ASC, id DESC
    """).fetchall()
    con.close()

    for r in rows:
        f = dict(r)
        kws = [
            k.strip().lower()
            for k in str(f.get("trigger_keywords") or "").split(",")
            if k.strip()
        ]
        for kw in kws:
            if kw and kw in text_norm:
                return f.get("funnel_key") or "", f.get("funnel_name") or "", kw

    return "", "", ""

def funnel_leads_upsert(item: dict):
    funnel_leads_init()

    source_platform = str(item.get("source_platform") or "instagram")
    source_table = str(item.get("source_table") or "")
    source_row_id = int(item.get("source_row_id") or 0)
    external_user_id = str(item.get("external_user_id") or "")
    username = str(item.get("username") or "")
    if not username:
        username = funnel_lead_extract_username(item.get("raw") or item)
    text = str(item.get("text") or "")

    matched_key = str(item.get("matched_funnel_key") or "")
    matched_name = str(item.get("matched_funnel_name") or "")

    if not matched_key:
        matched_key, matched_name, _kw = funnel_leads_match_funnel(text)

    now = dyn_now()

    con = dyn_con()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO funnel_leads (
            created_at, updated_at,
            source_platform, source_table, source_row_id,
            external_user_id, username, text,
            matched_funnel_key, matched_funnel_name,
            status, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_platform, source_table, source_row_id) DO UPDATE SET
            updated_at=excluded.updated_at,
            external_user_id=excluded.external_user_id,
            username=excluded.username,
            text=excluded.text,
            matched_funnel_key=CASE
                WHEN funnel_leads.matched_funnel_key='' OR funnel_leads.matched_funnel_key IS NULL
                THEN excluded.matched_funnel_key
                ELSE funnel_leads.matched_funnel_key
            END,
            matched_funnel_name=CASE
                WHEN funnel_leads.matched_funnel_name='' OR funnel_leads.matched_funnel_name IS NULL
                THEN excluded.matched_funnel_name
                ELSE funnel_leads.matched_funnel_name
            END,
            raw_json=excluded.raw_json
    """, (
        item.get("created_at") or now,
        now,
        source_platform,
        source_table,
        source_row_id,
        external_user_id,
        username,
        text,
        matched_key,
        matched_name,
        str(item.get("status") or "new"),
        json.dumps(item.get("raw") or item, ensure_ascii=False),
    ))

    con.commit()
    con.close()

def funnel_leads_ingest_from_existing(limit: int = 500):
    funnel_leads_init()
    limit = max(1, min(int(limit or 500), 5000))

    imported = {
        "ig_reactions": 0,
        "ig_ai_reply_drafts": 0,
        "instagram_webhook_messages": 0,
    }

    con = dyn_con()
    con.row_factory = sqlite3.Row

    # 1) ig_reactions
    try:
        rows = con.execute("""
            SELECT *
            FROM ig_reactions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        for r in rows:
            d = dict(r)
            funnel_leads_upsert({
                "created_at": d.get("created_at"),
                "source_platform": d.get("platform") or "instagram",
                "source_table": "ig_reactions",
                "source_row_id": d.get("id"),
                "external_user_id": d.get("external_user_id") or d.get("sender_id") or "",
                "username": d.get("username") or "",
                "text": d.get("reaction_text") or d.get("text") or d.get("comment_text") or "",
                "matched_funnel_key": d.get("matched_plan_key") or d.get("selected_funnel_plan_key") or "",
                "matched_funnel_name": d.get("matched_plan_name") or d.get("selected_funnel_plan_name") or "",
                "raw": d,
            })
            imported["ig_reactions"] += 1
    except Exception as e:
        imported["ig_reactions_error"] = str(e)

    # 2) ig_ai_reply_drafts
    try:
        rows = con.execute("""
            SELECT *
            FROM ig_ai_reply_drafts
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

        for r in rows:
            d = dict(r)
            funnel_leads_upsert({
                "created_at": d.get("created_at"),
                "source_platform": "instagram",
                "source_table": "ig_ai_reply_drafts",
                "source_row_id": d.get("id"),
                "external_user_id": d.get("external_user_id") or d.get("sender_id") or "",
                "username": d.get("username") or "",
                "text": d.get("incoming_text") or d.get("reaction_text") or d.get("direct_reply") or "",
                "matched_funnel_key": d.get("selected_funnel_plan_key") or "",
                "matched_funnel_name": d.get("selected_funnel_plan_name") or "",
                "raw": d,
            })
            imported["ig_ai_reply_drafts"] += 1
    except Exception as e:
        imported["ig_ai_reply_drafts_error"] = str(e)

    con.close()

    # 3) instagram_webhook_messages external DB
    try:
        if Path(IG_WEBHOOK_DB_PATH).exists():
            con_ig = sqlite3.connect(IG_WEBHOOK_DB_PATH)
            con_ig.row_factory = sqlite3.Row
            rows = con_ig.execute("""
                SELECT *
                FROM instagram_webhook_messages
                ORDER BY id DESC
                LIMIT ?
            """, (limit,)).fetchall()
            con_ig.close()

            for r in rows:
                d = dict(r)
                funnel_leads_upsert({
                    "created_at": d.get("created_at"),
                    "source_platform": "instagram",
                    "source_table": "instagram_webhook_messages",
                    "source_row_id": d.get("id"),
                    "external_user_id": d.get("sender_id") or "",
                    "username": "",
                    "text": d.get("text") or "",
                    "matched_funnel_key": "",
                    "matched_funnel_name": "",
                    "raw": d,
                })
                imported["instagram_webhook_messages"] += 1
    except Exception as e:
        imported["instagram_webhook_messages_error"] = str(e)

    return imported

@router.post("/leads/ingest")
def funnel_leads_ingest(payload: Dict[str, Any] = None):
    payload = payload or {}
    limit = int(payload.get("limit") or 500)
    imported = funnel_leads_ingest_from_existing(limit=limit)

    try:
        backup = _build_funnel_full_backup()
        snap = {"ok": True, "skipped": True, "reason": "after_leads_ingest_telegram_backup_disabled"}
    except Exception as e:
        snap = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "status": "ok",
        "imported": imported,
        "snapshot": snap,
    }

@router.get("/leads/list")
def funnel_leads_list(limit: int = 200, status: str = ""):
    funnel_leads_init()
    limit = max(1, min(int(limit or 200), 1000))

    con = dyn_con()
    con.row_factory = sqlite3.Row

    if status:
        rows = con.execute("""
            SELECT *
            FROM funnel_leads
            WHERE status=?
            ORDER BY id DESC
            LIMIT ?
        """, (status, limit)).fetchall()
    else:
        rows = con.execute("""
            SELECT *
            FROM funnel_leads
            ORDER BY id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    con.close()
    return {"ok": True, "status": "ok", "items": [dict(r) for r in rows]}

@router.post("/leads/{lead_id}/mark")
def funnel_lead_mark(lead_id: int, payload: Dict[str, Any]):
    funnel_leads_init()
    new_status = str(payload.get("status") or "processed").strip()

    con = dyn_con()
    cur = con.cursor()
    cur.execute("""
        UPDATE funnel_leads
        SET status=?, updated_at=?
        WHERE id=?
    """, (new_status, dyn_now(), int(lead_id)))
    changed = cur.rowcount
    con.commit()
    con.close()

    return {"ok": True, "status": "ok", "updated": changed, "lead_id": lead_id}

# Override runtime leads to use normalized funnel_leads inbox first
@router.get("/runtime/leads-v2")
def dyn_runtime_leads_v2(limit: int = 100):
    funnel_leads_ingest_from_existing(limit=500)
    return funnel_leads_list(limit=limit)

# === /FUNNEL LEAD INBOX V1 ===




# === FUNNEL AUTO SNAPSHOT V1 ===


# === FUNNEL AUTO SNAPSHOT SILENT V1 ===
def funnel_auto_snapshot_silent(reason="auto"):
    try:
        return _build_funnel_full_backup()
    except Exception as e:
        return {"ok": False, "error": str(e)}
# === /FUNNEL AUTO SNAPSHOT SILENT V1 ===

def _build_funnel_full_backup():
    dyn_init()

    con = dyn_con()
    con.row_factory = sqlite3.Row

    content_tables = {
        "funnel_configs": _dump_table(con, "funnel_configs", "priority ASC, id ASC"),
        "funnel_steps_dynamic": _dump_table(con, "funnel_steps_dynamic", "funnel_key ASC, step_order ASC, id ASC"),
        "funnel_sessions_dynamic": _dump_table(con, "funnel_sessions_dynamic", "id ASC"),
        "ig_reaction_funnel_plans": _dump_table(con, "ig_reaction_funnel_plans", "priority ASC, id ASC"),
        "ig_reactions": _dump_table(con, "ig_reactions", "id ASC"),
        "ig_ai_reply_drafts": _dump_table(con, "ig_ai_reply_drafts", "id ASC"),
    }

    con.close()

    ig_webhook_rows = []
    try:
        if Path(IG_WEBHOOK_DB_PATH).exists():
            con_ig = sqlite3.connect(IG_WEBHOOK_DB_PATH)
            con_ig.row_factory = sqlite3.Row
            ig_webhook_rows = _dump_table(con_ig, "instagram_webhook_messages", "id ASC")
            con_ig.close()
    except Exception as e:
        ig_webhook_rows = [{"_backup_error": str(e)}]

    return {
        "ok": True,
        "status": "ok",
        "backup_type": "funnels_full_v2",
        "exported_at": dyn_now(),
        "content_db": CONTENT_DB_PATH,
        "ig_webhook_db": IG_WEBHOOK_DB_PATH,
        "tables": {
            **content_tables,
            "instagram_webhook_messages": ig_webhook_rows,
        },
        "counts": {
            **{k: len(v) for k, v in content_tables.items()},
            "instagram_webhook_messages": len(ig_webhook_rows),
        }
    }

def _send_backup_json_to_telegram(backup_obj: dict, reason: str = "manual"):
    import tempfile
    import requests

    token = (
        os.getenv("TELEGRAM_BACKUP_BOT_TOKEN", "").strip()
        or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    )

    chat_id = (
        os.getenv("TELEGRAM_BACKUP_CHAT_ID", "").strip()
        or os.getenv("PLANNER_TELEGRAM_CHAT_ID", "").strip()
        or os.getenv("TELEGRAM_PLANNER_CHAT_ID", "").strip()
        or os.getenv("TELEGRAM_CHAT_ID", "").strip()
    )

    if not token or not chat_id:
        return {
            "ok": False,
            "skipped": True,
            "reason": "TELEGRAM_BACKUP_BOT_TOKEN/TELEGRAM_BOT_TOKEN or TELEGRAM_BACKUP_CHAT_ID missing",
        }

    ts = dyn_now().replace(":", "-")
    filename = f"funnels-backup-{reason}-{ts}.json"
    raw = json.dumps(backup_obj, ensure_ascii=False, indent=2)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(raw)
        tmp_path = f.name

    try:
        with open(tmp_path, "rb") as doc:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendDocument",
                data={
                    "chat_id": chat_id,
                    "caption": f"💾 Funnel backup\nreason={reason}\nexported_at={backup_obj.get('exported_at')}",
                },
                files={"document": (filename, doc, "application/json")},
                timeout=60,
            )

        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}

        return {
            "ok": bool(data.get("ok")),
            "status_code": r.status_code,
            "telegram": data,
        }
    finally:
        try:
            Path(tmp_path).unlink()
        except Exception:
            pass

@router.post("/backup/snapshot")
def funnels_backup_snapshot(payload: Dict[str, Any] = None):
    payload = payload or {}
    reason = str(payload.get("reason") or "manual").strip()[:80] or "manual"

    backup_obj = _build_funnel_full_backup()
    send_result = _send_backup_json_to_telegram(backup_obj, reason=reason)

    return {
        "ok": True,
        "status": "ok",
        "reason": reason,
        "counts": backup_obj.get("counts"),
        "sent_to_telegram": send_result,
    }

# === /FUNNEL AUTO SNAPSHOT V1 ===




# === TELEGRAM DB BACKUP EXTENSION V1 ===
TELEGRAM_DB_PATH = os.getenv("TELEGRAM_DB_PATH", os.path.join(os.getcwd(), "db", "telegram.sqlite"))

def _dump_sqlite_db_generic(db_path: str):
    out = {"db_path": db_path, "tables": {}, "schema": {}}
    try:
        if not Path(db_path).exists():
            out["missing"] = True
            return out

        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row

        tables = con.execute("""
            SELECT name, sql
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """).fetchall()

        for t in tables:
            name = t["name"]
            out["schema"][name] = t["sql"]
            rows = con.execute(f"SELECT * FROM {name}").fetchall()
            out["tables"][name] = [dict(r) for r in rows]

        con.close()
        return out
    except Exception as e:
        out["error"] = str(e)
        return out

def _restore_sqlite_db_generic(db_path: str, dump: dict):
    if not dump or not isinstance(dump, dict):
        return {"ok": False, "error": "empty dump"}

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(db_path)
    cur = con.cursor()

    restored = {}

    schema = dump.get("schema") or {}
    tables = dump.get("tables") or {}

    for table, create_sql in schema.items():
        if create_sql:
            cur.execute(create_sql)

    for table, rows in tables.items():
        if not rows:
            restored[table] = 0
            continue

        cols_existing = [r[1] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()]
        n = 0

        for row in rows:
            clean = {k: v for k, v in row.items() if k in cols_existing}
            if not clean:
                continue

            cols = list(clean.keys())
            placeholders = ",".join(["?"] * len(cols))
            col_sql = ",".join(cols)

            if "id" in clean:
                sql = f"INSERT OR REPLACE INTO {table} ({col_sql}) VALUES ({placeholders})"
            else:
                sql = f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})"

            cur.execute(sql, [clean[c] for c in cols])
            n += 1

        restored[table] = n

    con.commit()
    con.close()

    return {"ok": True, "restored": restored}

# === /TELEGRAM DB BACKUP EXTENSION V1 ===




# === MANUAL FUNNEL LEAD CREATE V1 ===
@router.post("/leads/create")
def funnel_lead_create(payload: Dict[str, Any]):
    funnel_leads_init()

    source_platform = str(payload.get("source_platform") or "instagram").strip()
    source_user_id = str(
        payload.get("source_user_id")
        or payload.get("external_user_id")
        or ""
    ).strip()
    source_username = str(
        payload.get("source_username")
        or payload.get("username")
        or source_user_id
        or ""
    ).strip()
    source_message = str(
        payload.get("source_message")
        or payload.get("text")
        or ""
    ).strip()

    if not source_user_id:
        return {
            "ok": False,
            "status": "error",
            "error": "source_user_id required",
        }

    matched_key = str(payload.get("matched_funnel_key") or "").strip()
    matched_name = str(payload.get("matched_funnel_name") or "").strip()

    if not matched_key:
        matched_key, matched_name, _kw = funnel_leads_match_funnel(source_message)

    now = dyn_now()
    raw = dict(payload)
    raw["manual_created"] = True

    con = dyn_con()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO funnel_leads (
            created_at, updated_at,
            source_platform, source_table, source_row_id,
            external_user_id, username, text,
            matched_funnel_key, matched_funnel_name,
            status, raw_json
        )
        VALUES (?, ?, ?, 'manual', 0, ?, ?, ?, ?, ?, ?, ?)
    """, (
        now,
        now,
        source_platform,
        source_user_id,
        source_username,
        source_message,
        matched_key,
        matched_name,
        str(payload.get("status") or "pending"),
        json.dumps(raw, ensure_ascii=False),
    ))

    lead_id = cur.lastrowid
    con.commit()
    con.close()

    try:
        snap = {"ok": True, "silent": True}
    except Exception as e:
        snap = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "status": "ok",
        "lead_id": lead_id,
        "source_user_id": source_user_id,
        "username": source_username,
        "text": source_message,
        "matched_funnel_key": matched_key,
        "matched_funnel_name": matched_name,
        "snapshot": snap,
    }

# === /MANUAL FUNNEL LEAD CREATE V1 ===




# === FUNNEL LEAD NAME ENRICH V1 ===
def funnel_lead_extract_username(raw: dict):
    if not isinstance(raw, dict):
        return ""

    for k in ["username", "source_username", "sender_username", "name", "full_name"]:
        v = raw.get(k)
        if v:
            return str(v)

    frm = raw.get("from") or {}
    if isinstance(frm, dict):
        return str(frm.get("username") or frm.get("name") or "")

    sender = raw.get("sender") or {}
    if isinstance(sender, dict):
        return str(sender.get("username") or sender.get("name") or "")

    return ""

def funnel_lead_graph_profile(user_id: str):
    token = (
        os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("IG_ACCESS_TOKEN", "").strip()
    )
    if not token or not user_id:
        return {}

    try:
        import requests
        ver = os.getenv("META_GRAPH_VERSION", "v20.0").strip() or "v20.0"
        r = requests.get(
            f"https://graph.facebook.com/{ver}/{user_id}",
            params={
                "fields": "id,username,name",
                "access_token": token,
            },
            timeout=15,
        )
        data = r.json()
        if isinstance(data, dict) and not data.get("error"):
            return data
    except Exception as e:
        print("[FUNNEL_LEAD_GRAPH_PROFILE_ERROR]", repr(e), flush=True)

    return {}

@router.post("/leads/enrich")
def funnel_leads_enrich(payload: Dict[str, Any] = None):
    payload = payload or {}
    limit = int(payload.get("limit") or 500)
    limit = max(1, min(limit, 2000))

    funnel_leads_init()

    con = dyn_con()
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT *
        FROM funnel_leads
        WHERE username='' OR username IS NULL OR username=external_user_id
        ORDER BY id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    updated = 0
    checked = 0

    for r in rows:
        checked += 1
        d = dict(r)
        raw = {}
        try:
            raw = json.loads(d.get("raw_json") or "{}")
        except Exception:
            raw = {}

        username = funnel_lead_extract_username(raw)

        if not username:
            profile = funnel_lead_graph_profile(d.get("external_user_id") or "")
            username = profile.get("username") or profile.get("name") or ""

        if username and username != d.get("username"):
            con.execute("""
                UPDATE funnel_leads
                SET username=?, updated_at=?
                WHERE id=?
            """, (username, dyn_now(), d["id"]))
            updated += 1

    con.commit()
    con.close()

    return {
        "ok": True,
        "status": "ok",
        "checked": checked,
        "updated": updated,
    }

# === /FUNNEL LEAD NAME ENRICH V1 ===

# === INSTAGRAM COMMENTS TO FUNNEL LEADS V1 ===
def ig_comments_token():
    return (
        os.getenv("FB_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("META_PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("PAGE_ACCESS_TOKEN", "").strip()
        or os.getenv("IG_ACCESS_TOKEN", "").strip()
    )

def ig_comments_graph_get(path: str, params: dict):
    import requests
    ver = os.getenv("META_GRAPH_VERSION", "v20.0").strip() or "v20.0"
    token = ig_comments_token()
    if not token:
        return {"ok": False, "error": "missing graph token"}

    url = f"https://graph.facebook.com/{ver}/{path.lstrip('/')}"
    q = dict(params or {})
    q["access_token"] = token

    r = requests.get(url, params=q, timeout=45)
    try:
        data = r.json()
    except Exception:
        data = {"raw": r.text}

    if r.status_code >= 300 or data.get("error"):
        return {
            "ok": False,
            "status_code": r.status_code,
            "error": data.get("error") or data,
            "url": url,
        }

    data["ok"] = True
    return data

def ig_comment_stable_row_id(comment_id: str):
    import zlib
    return int(zlib.crc32(str(comment_id or "").encode("utf-8")))

@router.post("/instagram/comments/sync")
def funnel_sync_instagram_comments(payload: Dict[str, Any] = None):
    """
    Pull Instagram media comments -> funnel_leads.
    Good for comments like "вага" under Reels/Post.
    """
    payload = payload or {}

    ig_user_id = str(
        payload.get("ig_user_id")
        or os.getenv("IG_USER_ID", "").strip()
    ).strip()

    if not ig_user_id:
        return {"ok": False, "status": "error", "error": "IG_USER_ID missing"}

    limit_media = max(1, min(int(payload.get("limit_media") or 20), 100))
    limit_comments = max(1, min(int(payload.get("limit_comments") or 50), 100))
    include_replies = int(payload.get("include_replies", 1))
    keyword = str(payload.get("keyword") or "").strip().lower()

    media_res = ig_comments_graph_get(
        f"{ig_user_id}/media",
        {
            "fields": "id,caption,media_type,permalink,timestamp,comments_count",
            "limit": str(limit_media),
        },
    )

    if not media_res.get("ok"):
        return {"ok": False, "stage": "media", "meta": media_res}

    funnel_leads_init()

    imported = 0
    matched = 0
    skipped = 0
    errors = []
    items = []

    for media in media_res.get("data") or []:
        media_id = str(media.get("id") or "")
        if not media_id:
            continue

        comments_res = ig_comments_graph_get(
            f"{media_id}/comments",
            {
                "fields": "id,text,username,timestamp,like_count,from",
                "limit": str(limit_comments),
            },
        )

        if not comments_res.get("ok"):
            errors.append({"media_id": media_id, "error": comments_res})
            continue

        comments = comments_res.get("data") or []

        for c in comments:
            text = str(c.get("text") or "").strip()
            if keyword and keyword not in text.lower():
                skipped += 1
                continue

            username = str(c.get("username") or "")
            frm = c.get("from") or {}
            if not username and isinstance(frm, dict):
                username = str(frm.get("username") or frm.get("name") or "")

            external_id = ""
            if isinstance(frm, dict):
                external_id = str(frm.get("id") or "")
            if not external_id:
                external_id = username or str(c.get("id") or "")

            matched_key, matched_name, matched_kw = funnel_leads_match_funnel(text)
            if matched_key:
                matched += 1

            item = {
                "created_at": c.get("timestamp") or dyn_now(),
                "source_platform": "instagram",
                "source_table": "instagram_comments",
                "source_row_id": ig_comment_stable_row_id(c.get("id")),
                "external_user_id": external_id,
                "username": username,
                "text": text,
                "matched_funnel_key": matched_key,
                "matched_funnel_name": matched_name,
                "status": "pending",
                "raw": {
                    "comment": c,
                    "media": media,
                    "matched_keyword": matched_kw,
                    "source_kind": "instagram_comment",
                },
            }

            lead_count_after = force_comment_lead_insert(item)
            imported += 1
            items.append({
                "media_id": media_id,
                "comment_id": c.get("id"),
                "username": username,
                "external_user_id": external_id,
                "text": text,
                "matched_funnel_key": matched_key,
                "matched_keyword": matched_kw,
            })

        if include_replies:
            # optional lightweight replies scan for comments we already got
            for c in comments:
                cid = str(c.get("id") or "")
                if not cid:
                    continue

                replies_res = ig_comments_graph_get(
                    f"{cid}/replies",
                    {
                        "fields": "id,text,username,timestamp,like_count,from",
                        "limit": "25",
                    },
                )

                if not replies_res.get("ok"):
                    continue

                for rep in replies_res.get("data") or []:
                    text = str(rep.get("text") or "").strip()
                    if keyword and keyword not in text.lower():
                        skipped += 1
                        continue

                    username = str(rep.get("username") or "")
                    frm = rep.get("from") or {}
                    if not username and isinstance(frm, dict):
                        username = str(frm.get("username") or frm.get("name") or "")

                    external_id = ""
                    if isinstance(frm, dict):
                        external_id = str(frm.get("id") or "")
                    if not external_id:
                        external_id = username or str(rep.get("id") or "")

                    matched_key, matched_name, matched_kw = funnel_leads_match_funnel(text)
                    if matched_key:
                        matched += 1

                    lead_count_after = force_comment_lead_insert({
                        "created_at": rep.get("timestamp") or dyn_now(),
                        "source_platform": "instagram",
                        "source_table": "instagram_comment_replies",
                        "source_row_id": ig_comment_stable_row_id(rep.get("id")),
                        "external_user_id": external_id,
                        "username": username,
                        "text": text,
                        "matched_funnel_key": matched_key,
                        "matched_funnel_name": matched_name,
                        "status": "pending",
                        "raw": {
                            "reply": rep,
                            "parent_comment": c,
                            "media": media,
                            "matched_keyword": matched_kw,
                            "source_kind": "instagram_comment_reply",
                        },
                    })

                    imported += 1
                    items.append({
                        "media_id": media_id,
                        "comment_id": rep.get("id"),
                        "username": username,
                        "external_user_id": external_id,
                        "text": text,
                        "matched_funnel_key": matched_key,
                        "matched_keyword": matched_kw,
                    })

    try:
        snap = {"ok": True, "silent": True}
    except Exception as e:
        snap = {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "status": "ok",
        "media_checked": len(media_res.get("data") or []),
        "imported": imported,
        "matched": matched,
        "skipped": skipped,
        "errors": errors[:5],
        "items": items[:100],
        "lead_count_after": lead_count_after,
        "snapshot": snap,
    }

# === /INSTAGRAM COMMENTS TO FUNNEL LEADS V1 ===




# === TELEGRAM BACKUP ALL PATHS V2 ===
def _possible_telegram_db_paths():
    raw = [
        os.getenv("TELEGRAM_DB_PATH", ""),
        os.getenv("TG_DB_PATH", ""),
        os.getenv("TELEGRAM_SQLITE_PATH", ""),
        os.path.join(os.getcwd(), "db", "telegram.sqlite"),
        os.path.join(os.getcwd(), "telegram.sqlite"),
        os.path.join(os.getcwd(), "data", "telegram.sqlite"),
        os.path.join(os.getcwd(), "data", "content.db"),
        CONTENT_DB_PATH,
    ]
    out = []
    for x in raw:
        x = str(x or "").strip()
        if x and x not in out:
            out.append(x)
    return out

def _dump_telegram_related_from_content_db():
    con = dyn_con()
    con.row_factory = sqlite3.Row
    out = {"tables": {}, "schema": {}}

    rows = con.execute("""
        SELECT name, sql
        FROM sqlite_master
        WHERE type='table'
          AND (
            lower(name) LIKE '%telegram%'
            OR lower(name) LIKE '%tg_%'
            OR lower(name) LIKE 'tg%'
          )
        ORDER BY name
    """).fetchall()

    for r in rows:
        name = r["name"]
        out["schema"][name] = r["sql"]
        try:
            data = con.execute(f"SELECT * FROM {name}").fetchall()
            out["tables"][name] = [dict(x) for x in data]
        except Exception as e:
            out["tables"][name] = [{"_error": str(e)}]

    con.close()
    return out

def build_telegram_backup_bundle():
    bundle = {
        "content_db_telegram_tables": _dump_telegram_related_from_content_db(),
        "sqlite_files": {},
        "paths_checked": _possible_telegram_db_paths(),
    }

    for path in _possible_telegram_db_paths():
        try:
            if Path(path).exists():
                bundle["sqlite_files"][path] = _dump_sqlite_db_generic(path)
        except Exception as e:
            bundle["sqlite_files"][path] = {"error": str(e), "db_path": path}

    return bundle

def restore_telegram_backup_bundle(bundle: dict):
    result = {"content_db": {}, "sqlite_files": {}}
    if not isinstance(bundle, dict):
        return {"ok": False, "error": "telegram backup bundle missing"}

    # restore telegram-related tables into content DB
    cdb = bundle.get("content_db_telegram_tables") or {}
    schema = cdb.get("schema") or {}
    tables = cdb.get("tables") or {}

    con = dyn_con()
    cur = con.cursor()

    for table, create_sql in schema.items():
        if create_sql:
            try:
                cur.execute(create_sql)
            except Exception as e:
                result["content_db"][table + "_schema_error"] = str(e)

    for table, rows in tables.items():
        try:
            result["content_db"][table] = _insert_or_replace_rows(con, table, rows, preserve_id=True)
        except Exception as e:
            result["content_db"][table + "_error"] = str(e)

    con.commit()
    con.close()

    # restore sqlite files only for current configured paths, not old Render absolute paths
    files = bundle.get("sqlite_files") or {}
    current_paths = _possible_telegram_db_paths()

    for target_path in current_paths:
        # pick first dump that has telegram-looking tables
        chosen = None
        for _old_path, dump in files.items():
            if isinstance(dump, dict) and dump.get("tables"):
                chosen = dump
                break
        if chosen:
            result["sqlite_files"][target_path] = _restore_sqlite_db_generic(target_path, chosen)

    return {"ok": True, "restored": result}

# === /TELEGRAM BACKUP ALL PATHS V2 ===




# === FORCE COMMENT LEAD INSERT V1 ===
def force_comment_lead_insert(item: dict):
    funnel_leads_init()

    now = dyn_now()
    con = dyn_con()
    cur = con.cursor()

    cur.execute("""
        INSERT INTO funnel_leads (
            created_at, updated_at,
            source_platform, source_table, source_row_id,
            external_user_id, username, text,
            matched_funnel_key, matched_funnel_name,
            status, raw_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(source_platform, source_table, source_row_id) DO UPDATE SET
            updated_at=excluded.updated_at,
            external_user_id=excluded.external_user_id,
            username=excluded.username,
            text=excluded.text,
            matched_funnel_key=excluded.matched_funnel_key,
            matched_funnel_name=excluded.matched_funnel_name,
            status=CASE
                WHEN funnel_leads.status='' OR funnel_leads.status IS NULL THEN excluded.status
                ELSE funnel_leads.status
            END,
            raw_json=excluded.raw_json
    """, (
        item.get("created_at") or now,
        now,
        str(item.get("source_platform") or "instagram"),
        str(item.get("source_table") or "instagram_comments"),
        int(item.get("source_row_id") or 0),
        str(item.get("external_user_id") or ""),
        str(item.get("username") or ""),
        str(item.get("text") or ""),
        str(item.get("matched_funnel_key") or ""),
        str(item.get("matched_funnel_name") or ""),
        str(item.get("status") or "pending"),
        json.dumps(item.get("raw") or item, ensure_ascii=False),
    ))

    con.commit()

    cnt = con.execute("SELECT COUNT(*) FROM funnel_leads").fetchone()[0]
    con.close()
    return cnt

# === /FORCE COMMENT LEAD INSERT V1 ===




# === FUNNELS SEED FROM REACTION PLANS SAFE V2 ===
@router.post("/backup/seed_from_reaction_plans")
def funnels_seed_from_reaction_plans_safe_v2():
    con = db()
    con.row_factory = sqlite3.Row
    imported = 0
    try:
        con.execute("""
        CREATE TABLE IF NOT EXISTS funnel_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funnel_key TEXT UNIQUE,
            name TEXT,
            active INTEGER DEFAULT 1,
            trigger_type TEXT DEFAULT 'keyword',
            trigger_value TEXT DEFAULT '',
            telegram_bot_username TEXT DEFAULT '',
            telegram_channel_url TEXT DEFAULT '',
            target_url TEXT DEFAULT '',
            dm_template TEXT DEFAULT '',
            ai_prompt TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        plans = con.execute("""
            SELECT *
            FROM ig_reaction_funnel_plans
            WHERE COALESCE(active, 1)=1
            ORDER BY priority ASC, id ASC
        """).fetchall()

        for p in plans:
            key = str(p["plan_key"] or "").strip()
            if not key:
                continue

            con.execute("""
            INSERT INTO funnel_configs
            (funnel_key, name, active, trigger_type, trigger_value,
             telegram_bot_username, telegram_channel_url, target_url,
             dm_template, ai_prompt, created_at, updated_at)
            VALUES (?, ?, 1, 'keyword', ?, '', '', '', ?, ?, datetime('now'), datetime('now'))
            ON CONFLICT(funnel_key) DO UPDATE SET
              name=excluded.name,
              active=1,
              trigger_type='keyword',
              trigger_value=excluded.trigger_value,
              dm_template=excluded.dm_template,
              ai_prompt=excluded.ai_prompt,
              updated_at=datetime('now')
            """, (
                key,
                str(p["plan_name"] or key),
                str(p["trigger_keywords"] or ""),
                str(p["direct_cta"] or p["public_cta"] or ""),
                (str(p["plan_goal"] or "") + "\\n\\n" + str(p["notes"] or "")).strip()
            ))
            imported += 1

        con.commit()
        return {"ok": True, "status": "ok", "imported": imported}
    except Exception as e:
        return {"ok": False, "status": "error", "error": repr(e)}
    finally:
        con.close()
# === /FUNNELS SEED FROM REACTION PLANS SAFE V2 ===

# === FUNNEL LEADS CLEAN REMATCH V1 ===
@router.post("/leads/mark-own-and-rematch")
def funnel_leads_mark_own_and_rematch(payload: Dict[str, Any] = None):
    payload = payload or {}
    own_usernames = set(str(x).strip().lower() for x in (payload.get("own_usernames") or []) if str(x).strip())
    own_ids = set(str(x).strip() for x in (payload.get("own_ids") or []) if str(x).strip())

    if not own_usernames:
        env_names = os.getenv("IG_OWN_USERNAMES", "")
        own_usernames |= set(x.strip().lower() for x in env_names.split(",") if x.strip())

    if not own_ids:
        env_ids = os.getenv("IG_OWN_IDS", "")
        own_ids |= set(x.strip() for x in env_ids.split(",") if x.strip())

    funnel_leads_init()

    con = dyn_con()
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT *
        FROM funnel_leads
        ORDER BY id DESC
        LIMIT 5000
    """).fetchall()

    own_marked = 0
    rematched = 0

    for r in rows:
        d = dict(r)
        username = str(d.get("username") or "").lower().strip()
        external_id = str(d.get("external_user_id") or "").strip()
        text = str(d.get("text") or "")

        is_own = (username and username in own_usernames) or (external_id and external_id in own_ids)

        if is_own:
            con.execute("""
                UPDATE funnel_leads
                SET status='own_ignored',
                    updated_at=?
                WHERE id=?
            """, (dyn_now(), d["id"]))
            own_marked += 1
            continue

        matched_key, matched_name, _kw = funnel_leads_match_funnel(text)
        if matched_key and matched_key != (d.get("matched_funnel_key") or ""):
            con.execute("""
                UPDATE funnel_leads
                SET matched_funnel_key=?,
                    matched_funnel_name=?,
                    updated_at=?
                WHERE id=?
            """, (matched_key, matched_name, dyn_now(), d["id"]))
            rematched += 1

    con.commit()
    con.close()

    return {
        "ok": True,
        "status": "ok",
        "own_marked": own_marked,
        "rematched": rematched,
        "own_usernames": sorted(own_usernames),
        "own_ids": sorted(own_ids),
    }

# === /FUNNEL LEADS CLEAN REMATCH V1 ===


# === RESTORE LOCAL FUNNELS BUNDLE V1 ===
@router.post("/restore/local_bundle")
def restore_local_funnels_bundle_v1():
    try:
        import json
        from pathlib import Path

        bundle_path = Path("/tmp/funnels-local-merged.json")

        if not bundle_path.exists():
            return {
                "ok": False,
                "status": "error",
                "error": "local bundle not found",
                "path": str(bundle_path)
            }

        payload = json.loads(bundle_path.read_text(encoding="utf-8"))

        # Telegram restore окремий
        payload.pop("telegram_db", None)
        payload.pop("telegram_bundle", None)

        return funnels_backup_import_full(payload)

    except Exception as e:
        return {
            "ok": False,
            "status": "error",
            "where": "restore_local_bundle",
            "error": repr(e)
        }
# === /RESTORE LOCAL FUNNELS BUNDLE V1 ===



# === CONVERT LEGACY FUNNEL EVENTS TO DYNAMIC V1 ===
@router.post("/restore/convert_legacy_events")
def convert_legacy_funnel_events_to_dynamic_v1():
    import json, sqlite3
    from pathlib import Path

    con = dyn_con()
    con.row_factory = sqlite3.Row
    created_configs = 0
    created_steps = 0

    try:
        # читаємо legacy events напряму з локального merged bundle
        bundle_path = Path("/tmp/funnels-local-merged.json")
        if not bundle_path.exists():
            return {"ok": False, "status": "error", "error": "bundle file not found", "path": str(bundle_path)}

        payload = json.loads(bundle_path.read_text(encoding="utf-8"))
        legacy_events = (payload.get("tables") or {}).get("funnel_events") or []

        if not legacy_events:
            return {"ok": False, "status": "error", "error": "no funnel_events in bundle"}

        # гарантуємо/мігруємо колонки існуючих таблиць
        def _cols(table):
            try:
                return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
            except Exception:
                return []

        def _add_col(table, col, ddl):
            if col not in _cols(table):
                try:
                    con.execute(f'ALTER TABLE "{table}" ADD COLUMN {ddl}')
                except Exception:
                    pass

        _add_col("funnel_configs", "name", "name TEXT DEFAULT ''")
        _add_col("funnel_configs", "trigger_type", "trigger_type TEXT DEFAULT 'keyword'")
        _add_col("funnel_configs", "trigger_value", "trigger_value TEXT DEFAULT ''")
        _add_col("funnel_configs", "telegram_bot_username", "telegram_bot_username TEXT DEFAULT ''")
        _add_col("funnel_configs", "telegram_channel_url", "telegram_channel_url TEXT DEFAULT ''")
        _add_col("funnel_configs", "target_url", "target_url TEXT DEFAULT ''")
        _add_col("funnel_configs", "dm_template", "dm_template TEXT DEFAULT ''")
        _add_col("funnel_configs", "ai_prompt", "ai_prompt TEXT DEFAULT ''")
        _add_col("funnel_configs", "created_at", "created_at TEXT DEFAULT CURRENT_TIMESTAMP")
        _add_col("funnel_configs", "updated_at", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP")

        _add_col("funnel_steps_dynamic", "name", "name TEXT DEFAULT ''")
        _add_col("funnel_steps_dynamic", "message_template", "message_template TEXT DEFAULT ''")
        _add_col("funnel_steps_dynamic", "delay_seconds", "delay_seconds INTEGER DEFAULT 0")
        _add_col("funnel_steps_dynamic", "config_json", "config_json TEXT DEFAULT '{}'")
        _add_col("funnel_steps_dynamic", "created_at", "created_at TEXT DEFAULT CURRENT_TIMESTAMP")
        _add_col("funnel_steps_dynamic", "updated_at", "updated_at TEXT DEFAULT CURRENT_TIMESTAMP")

        # гарантуємо нові таблиці конструктора
        con.execute("""
        CREATE TABLE IF NOT EXISTS funnel_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funnel_key TEXT UNIQUE,
            name TEXT,
            active INTEGER DEFAULT 1,
            trigger_type TEXT DEFAULT 'keyword',
            trigger_value TEXT DEFAULT '',
            telegram_bot_username TEXT DEFAULT '',
            telegram_channel_url TEXT DEFAULT '',
            target_url TEXT DEFAULT '',
            dm_template TEXT DEFAULT '',
            ai_prompt TEXT DEFAULT '',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS funnel_steps_dynamic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            funnel_key TEXT,
            step_key TEXT,
            step_order INTEGER DEFAULT 1,
            step_type TEXT DEFAULT 'send_message',
            name TEXT DEFAULT '',
            message_template TEXT DEFAULT '',
            delay_seconds INTEGER DEFAULT 0,
            config_json TEXT DEFAULT '{}',
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(funnel_key, step_key)
        )
        """)

        rows = [x for x in legacy_events if x.get("event_type") in ("funnel_created","funnel_updated","funnel_step_upserted","step_upserted")]
        funnel_ids = sorted(set([str(x.get("funnel_id")) for x in rows if x.get("funnel_id") is not None]))

        for fid in funnel_ids:
            key = "legacy_funnel_" + str(fid)

            exists = con.execute("SELECT id FROM funnel_configs WHERE funnel_key=? LIMIT 1", (key,)).fetchone()
            if not exists:
                con.execute("""
                    INSERT INTO funnel_configs
                    (funnel_key, name, active, trigger_type, trigger_value,
                     telegram_bot_username, telegram_channel_url, target_url,
                     dm_template, ai_prompt, created_at, updated_at)
                    VALUES (?, ?, 1, 'keyword', 'вага', '', '', '',
                            'Напиши в direct слово ВАГА — і я підкажу наступний крок.',
                            'Legacy funnel restored from /tmp/funnels-local-merged.json',
                            datetime('now'), datetime('now'))
                """, (key, "Відновлена воронка #" + str(fid)))
                created_configs += 1

            step_rows = [r for r in rows if str(r.get("funnel_id")) == str(fid) and r.get("event_type") in ("funnel_step_upserted","step_upserted")]

            for idx, r in enumerate(step_rows, start=1):
                try:
                    pl = json.loads(r.get("payload_json") or "{}")
                except Exception:
                    pl = {}

                step_id = pl.get("step_id") or idx
                step_order = pl.get("step_order") or idx
                step_type = pl.get("step_type") or "send_message"
                step_name = pl.get("step_name") or ("Крок " + str(step_order))
                cfg = pl.get("config") or {}

                msg = cfg.get("text") or cfg.get("message") or cfg.get("prompt") or cfg.get("title") or ""

                con.execute("""
                    INSERT INTO funnel_steps_dynamic
                    (funnel_key, step_key, step_order, step_type, name,
                     message_template, delay_seconds, config_json, active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                    ON CONFLICT(funnel_key, step_key) DO UPDATE SET
                      step_order=excluded.step_order,
                      step_type=excluded.step_type,
                      name=excluded.name,
                      message_template=excluded.message_template,
                      delay_seconds=excluded.delay_seconds,
                      config_json=excluded.config_json,
                      active=1,
                      updated_at=datetime('now')
                """, (
                    key,
                    "legacy_step_" + str(step_id),
                    int(step_order or idx),
                    str(step_type),
                    str(step_name),
                    str(msg),
                    int(cfg.get("delay_seconds") or cfg.get("delay") or 0),
                    json.dumps(cfg, ensure_ascii=False),
                ))
                created_steps += 1

        con.commit()
        return {
            "ok": True,
            "status": "ok",
            "source": str(bundle_path),
            "legacy_events": len(legacy_events),
            "legacy_funnels": len(funnel_ids),
            "created_configs": created_configs,
            "created_steps": created_steps,
        }

    except Exception as e:
        return {"ok": False, "status": "error", "where": "convert_legacy_events_json", "error": repr(e)}
    finally:
        con.close()
# === /CONVERT LEGACY FUNNEL EVENTS TO DYNAMIC V1 ===

# === FUNNEL LEADS DEBUG LIST V1 ===
@router.get("/leads/debug-list")
def funnel_leads_debug_list(limit: int = 50):
    funnel_leads_init()
    con = dyn_con()
    con.row_factory = sqlite3.Row

    count = con.execute("SELECT COUNT(*) AS n FROM funnel_leads").fetchone()["n"]
    rows = con.execute("""
        SELECT *
        FROM funnel_leads
        ORDER BY id DESC
        LIMIT ?
    """, (int(limit),)).fetchall()

    con.close()

    return {
        "ok": True,
        "count": count,
        "items": [dict(r) for r in rows],
        "db_path": CONTENT_DB_PATH,
    }

# === /FUNNEL LEADS DEBUG LIST V1 ===


# === CONVERT LEGACY FUNNEL EVENTS FROM DB V1 ===
@router.post("/restore/convert_legacy_events_db")
def convert_legacy_funnel_events_from_db_v1():
    import json, sqlite3
    con = dyn_con()
    con.row_factory = sqlite3.Row
    created_configs = 0
    created_steps = 0

    try:
        # ensure columns/tables
        def _cols(table):
            try:
                return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")').fetchall()]
            except Exception:
                return []

        def _add_col(table, col, ddl):
            if col not in _cols(table):
                try:
                    con.execute(f'ALTER TABLE "{table}" ADD COLUMN {ddl}')
                except Exception:
                    pass

        con.execute("""
        CREATE TABLE IF NOT EXISTS funnel_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
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

        con.execute("""
        CREATE TABLE IF NOT EXISTS funnel_steps_dynamic (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
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

        _add_col("funnel_configs", "name", "name TEXT DEFAULT ''")
        _add_col("funnel_configs", "trigger_type", "trigger_type TEXT DEFAULT 'keyword'")
        _add_col("funnel_configs", "trigger_value", "trigger_value TEXT DEFAULT ''")
        _add_col("funnel_configs", "ai_prompt", "ai_prompt TEXT DEFAULT ''")

        _add_col("funnel_steps_dynamic", "step_type", "step_type TEXT DEFAULT 'send_message'")
        _add_col("funnel_steps_dynamic", "name", "name TEXT DEFAULT ''")
        _add_col("funnel_steps_dynamic", "message_template", "message_template TEXT DEFAULT ''")
        _add_col("funnel_steps_dynamic", "delay_seconds", "delay_seconds INTEGER DEFAULT 0")
        _add_col("funnel_steps_dynamic", "config_json", "config_json TEXT DEFAULT '{}'")

        # read imported legacy table from Render DB
        try:
            legacy_events = [dict(r) for r in con.execute('SELECT * FROM funnel_events ORDER BY id ASC').fetchall()]
        except Exception as e:
            return {"ok": False, "status": "error", "error": "funnel_events table missing", "details": repr(e)}

        rows = [x for x in legacy_events if x.get("event_type") in ("funnel_created","funnel_updated","funnel_step_upserted","step_upserted")]
        funnel_ids = sorted(set([str(x.get("funnel_id")) for x in rows if x.get("funnel_id") is not None]))

        for fid in funnel_ids:
            key = "legacy_funnel_" + str(fid)

            exists = con.execute("SELECT id FROM funnel_configs WHERE funnel_key=? LIMIT 1", (key,)).fetchone()
            if not exists:
                con.execute("""
                    INSERT INTO funnel_configs
                    (funnel_key, funnel_name, name, active, trigger_type, trigger_value, trigger_keywords,
                     dm_template, ai_prompt, created_at, updated_at)
                    VALUES (?, ?, ?, 1, 'keyword', 'вага', 'вага',
                            'Напиши в direct слово ВАГА — і я підкажу наступний крок.',
                            'Legacy funnel restored from imported funnel_events',
                            datetime('now'), datetime('now'))
                """, (key, "Відновлена воронка #" + str(fid), "Відновлена воронка #" + str(fid)))
                created_configs += 1

            step_rows = [r for r in rows if str(r.get("funnel_id")) == str(fid) and r.get("event_type") in ("funnel_step_upserted","step_upserted")]

            for idx, r in enumerate(step_rows, start=1):
                try:
                    pl = json.loads(r.get("payload_json") or "{}")
                except Exception:
                    pl = {}

                step_id = pl.get("step_id") or idx
                step_order = pl.get("step_order") or idx
                step_type = pl.get("step_type") or "send_message"
                step_name = pl.get("step_name") or ("Крок " + str(step_order))
                cfg = pl.get("config") or {}

                msg = cfg.get("text") or cfg.get("message") or cfg.get("prompt") or cfg.get("title") or ""

                con.execute("""
                    INSERT INTO funnel_steps_dynamic
                    (funnel_key, step_key, step_order, step_type, name,
                     message_template, message_text, delay_seconds, delay_minutes,
                     config_json, settings_json, active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, datetime('now'), datetime('now'))
                    ON CONFLICT(funnel_key, step_key) DO UPDATE SET
                      step_order=excluded.step_order,
                      step_type=excluded.step_type,
                      name=excluded.name,
                      message_template=excluded.message_template,
                      message_text=excluded.message_text,
                      delay_seconds=excluded.delay_seconds,
                      delay_minutes=excluded.delay_minutes,
                      config_json=excluded.config_json,
                      settings_json=excluded.settings_json,
                      active=1,
                      updated_at=datetime('now')
                """, (
                    key,
                    "legacy_step_" + str(step_id),
                    int(step_order or idx),
                    str(step_type),
                    str(step_name),
                    str(msg),
                    str(msg),
                    int(cfg.get("delay_seconds") or cfg.get("delay") or 0),
                    int((cfg.get("delay_seconds") or cfg.get("delay") or 0) // 60) if isinstance((cfg.get("delay_seconds") or cfg.get("delay") or 0), int) else 0,
                    json.dumps(cfg, ensure_ascii=False),
                    json.dumps(cfg, ensure_ascii=False),
                ))
                created_steps += 1

        con.commit()
        return {
            "ok": True,
            "status": "ok",
            "source": "render_db.funnel_events",
            "legacy_events": len(legacy_events),
            "legacy_funnels": len(funnel_ids),
            "created_configs": created_configs,
            "created_steps": created_steps,
        }
    except Exception as e:
        return {"ok": False, "status": "error", "where": "convert_legacy_events_db", "error": repr(e)}
    finally:
        con.close()
# === /CONVERT LEGACY FUNNEL EVENTS FROM DB V1 ===


# === PUSH LATEST LOCAL FUNNELS BACKUP TO RENDER V1 ===
@router.post("/restore/push_latest_local_to_render")
def push_latest_local_funnels_backup_to_render_v1():
    try:
        import json, os, urllib.request
        from pathlib import Path

        candidates = []
        search_dirs = [
            Path.home() / "Downloads",
            Path("/tmp"),
            Path.cwd()
        ]

        for d in search_dirs:
            if not d.exists():
                continue
            candidates += list(d.glob("funnels-autobackup*.json"))
            candidates += list(d.glob("funnels-local-merged*.json"))
            candidates += list(d.glob("funnels-backup*.json"))

        if not candidates:
            return {"ok": False, "status": "error", "error": "no local funnels backup json found"}

        latest = max(candidates, key=lambda x: x.stat().st_mtime)
        payload = json.loads(latest.read_text(encoding="utf-8"))

        payload.pop("telegram_db", None)
        payload.pop("telegram_bundle", None)

        render_url = os.getenv("RENDER_API", "https://content-ai-ps1k.onrender.com").rstrip("/")
        req = urllib.request.Request(
            render_url + "/api/funnels/backup/import",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")

        try:
            data = json.loads(body)
        except Exception:
            data = {"raw": body}

        return {
            "ok": True,
            "status": "ok",
            "local_file": str(latest),
            "render_url": render_url,
            "render_response": data
        }

    except Exception as e:
        return {"ok": False, "status": "error", "where": "push_latest_local_to_render", "error": repr(e)}
# === /PUSH LATEST LOCAL FUNNELS BACKUP TO RENDER V1 ===


# === FIXED LOCAL FUNNELS BACKUP FILE V1 ===
@router.post("/backup/save_render_to_local")
def save_render_funnels_backup_to_local_v1():
    try:
        import json, os, urllib.request
        from pathlib import Path

        render_url = os.getenv("RENDER_API", "https://content-ai-ps1k.onrender.com").rstrip("/")
        backup_path = Path(os.getenv("FUNNELS_LOCAL_BACKUP_PATH", "backups/funnels-latest.json"))
        backup_path.parent.mkdir(parents=True, exist_ok=True)

        with urllib.request.urlopen(render_url + "/api/funnels/backup/export", timeout=60) as resp:
            body = resp.read().decode("utf-8")

        data = json.loads(body)

        # Telegram backup окремий
        data.pop("telegram_db", None)
        data.pop("telegram_bundle", None)

        backup_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "ok": True,
            "status": "ok",
            "saved_to": str(backup_path),
            "render_url": render_url,
            "backup_type": data.get("backup_type"),
            "tables": {k: len(v or []) for k, v in (data.get("tables") or {}).items()}
        }

    except Exception as e:
        return {"ok": False, "status": "error", "where": "save_render_to_local", "error": repr(e)}


@router.post("/restore/push_local_to_render")
def push_fixed_local_funnels_backup_to_render_v1():
    try:
        import json, os, urllib.request
        from pathlib import Path

        render_url = os.getenv("RENDER_API", "https://content-ai-ps1k.onrender.com").rstrip("/")
        backup_path = Path(os.getenv("FUNNELS_LOCAL_BACKUP_PATH", "backups/funnels-latest.json"))

        if not backup_path.exists():
            return {
                "ok": False,
                "status": "error",
                "error": "fixed local backup file not found",
                "path": str(backup_path)
            }

        data = json.loads(backup_path.read_text(encoding="utf-8"))

        # Telegram backup окремий
        data.pop("telegram_db", None)
        data.pop("telegram_bundle", None)

        req = urllib.request.Request(
            render_url + "/api/funnels/backup/import",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")

        try:
            render_response = json.loads(body)
        except Exception:
            render_response = {"raw": body}

        return {
            "ok": True,
            "status": "ok",
            "pushed_from": str(backup_path),
            "render_url": render_url,
            "render_response": render_response
        }

    except Exception as e:
        return {"ok": False, "status": "error", "where": "push_local_to_render", "error": repr(e)}
# === /FIXED LOCAL FUNNELS BACKUP FILE V1 ===


# === AUTO BACKUP ALL SYSTEM DATA V1 ===
@router.post("/backup/auto_save_all")
def auto_save_all_system_backups_v1():
    try:
        import json, os, urllib.request
        from pathlib import Path

        render_url = os.getenv("RENDER_API", "https://content-ai-ps1k.onrender.com").rstrip("/")

        backup_dir = Path(os.getenv("SYSTEM_BACKUP_DIR", "backups"))
        backup_dir.mkdir(parents=True, exist_ok=True)

        results = {}

        # FUNNELS
        try:
            with urllib.request.urlopen(render_url + "/api/funnels/backup/export", timeout=60) as resp:
                funnels = json.loads(resp.read().decode("utf-8"))

            funnels.pop("telegram_db", None)
            funnels.pop("telegram_bundle", None)

            funnels_path = backup_dir / "funnels-latest.json"
            funnels_path.write_text(json.dumps(funnels, ensure_ascii=False, indent=2), encoding="utf-8")

            results["funnels"] = {
                "ok": True,
                "path": str(funnels_path)
            }
        except Exception as e:
            results["funnels"] = {"ok": False, "error": repr(e)}

        # TELEGRAM
        try:
            with urllib.request.urlopen(render_url + "/api/telegram/backup/export", timeout=60) as resp:
                tg = json.loads(resp.read().decode("utf-8"))

            tg_path = backup_dir / "telegram-latest.json"
            tg_path.write_text(json.dumps(tg, ensure_ascii=False, indent=2), encoding="utf-8")

            results["telegram"] = {
                "ok": True,
                "path": str(tg_path)
            }
        except Exception as e:
            results["telegram"] = {"ok": False, "error": repr(e)}

        # FULL
        full = {
            "saved_at": time.time(),
            "funnels": results.get("funnels"),
            "telegram": results.get("telegram"),
        }

        full_path = backup_dir / "full-system-backup.json"
        full_path.write_text(json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "ok": True,
            "status": "ok",
            "backup_dir": str(backup_dir),
            "results": results,
            "full_backup": str(full_path)
        }

    except Exception as e:
        return {"ok": False, "status": "error", "where": "auto_save_all", "error": repr(e)}
# === /AUTO BACKUP ALL SYSTEM DATA V1 ===


# === IMPORT LEGACY FUNNEL EVENTS PAYLOAD V1 ===
@router.post("/restore/import_legacy_payload")
def import_legacy_funnel_payload_v1(payload: Dict[str, Any]):
    import json, sqlite3
    con = dyn_con()
    con.row_factory = sqlite3.Row
    try:
        tables = payload.get("tables") or {}

        legacy_tables = ["funnel_events", "funnel_contacts", "funnel_jobs", "funnel_leads", "ig_reactions", "ig_ai_reply_drafts"]
        imported = {}

        for table_name in legacy_tables:
            rows = tables.get(table_name) or []
            imported[table_name] = 0
            if not rows:
                continue

            cols = list(rows[0].keys())
            defs = []
            for c in cols:
                if c == "id":
                    defs.append('"id" INTEGER PRIMARY KEY')
                else:
                    defs.append(f'"{c}" TEXT')
            con.execute(f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(defs)})')

            for r in rows:
                keys = list(r.keys())
                cols_sql = ",".join([f'"{k}"' for k in keys])
                placeholders = ",".join(["?"] * len(keys))
                vals = [r.get(k) for k in keys]

                # id-based upsert fallback
                if "id" in r:
                    con.execute(f'DELETE FROM "{table_name}" WHERE id=?', (r.get("id"),))

                con.execute(f'INSERT INTO "{table_name}" ({cols_sql}) VALUES ({placeholders})', vals)
                imported[table_name] += 1

        con.commit()
        return {"ok": True, "status": "ok", "imported": imported}
    except Exception as e:
        return {"ok": False, "status": "error", "where": "import_legacy_payload", "error": repr(e)}
    finally:
        con.close()
# === /IMPORT LEGACY FUNNEL EVENTS PAYLOAD V1 ===


# === CONVERT IG REACTIONS TO FUNNEL LEADS V1 ===
@router.post("/restore/convert_ig_reactions_to_leads")
def convert_ig_reactions_to_funnel_leads_v1():
    import sqlite3, json
    con = dyn_con()
    con.row_factory = sqlite3.Row
    imported = 0
    skipped = 0

    try:
        con.execute("""
        CREATE TABLE IF NOT EXISTS funnel_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            source TEXT DEFAULT 'instagram',
            platform TEXT DEFAULT 'instagram',
            external_user_id TEXT,
            username TEXT DEFAULT '',
            source_message TEXT DEFAULT '',
            source_event_id TEXT DEFAULT '',
            matched_plan_key TEXT DEFAULT '',
            lead_status TEXT DEFAULT 'new',
            raw_json TEXT DEFAULT ''
        )
        """)

        rows = con.execute("SELECT * FROM ig_reactions ORDER BY id ASC").fetchall()

        for r in rows:
            uid = str(r["external_user_id"] or "").strip() if "external_user_id" in r.keys() else ""
            msg = str(r["reaction_text"] or "").strip() if "reaction_text" in r.keys() else ""
            eid = str(r["external_event_id"] or "").strip() if "external_event_id" in r.keys() else ""

            if not uid and not msg:
                skipped += 1
                continue

            exists = con.execute("""
                SELECT id FROM funnel_leads
                WHERE COALESCE(source_event_id,'') = ?
                   OR (COALESCE(external_user_id,'') = ? AND COALESCE(source_message,'') = ?)
                LIMIT 1
            """, (eid, uid, msg)).fetchone()

            if exists:
                skipped += 1
                continue

            con.execute("""
                INSERT INTO funnel_leads
                (created_at, updated_at, source, platform, external_user_id, username,
                 source_message, source_event_id, matched_plan_key, lead_status, raw_json)
                VALUES (?, CURRENT_TIMESTAMP, 'instagram', 'instagram', ?, ?, ?, ?, ?, 'new', ?)
            """, (
                r["created_at"] if "created_at" in r.keys() else None,
                uid,
                r["username"] if "username" in r.keys() else "",
                msg,
                eid,
                r["matched_plan_key"] if "matched_plan_key" in r.keys() else "",
                json.dumps(dict(r), ensure_ascii=False),
            ))
            imported += 1

        con.commit()
        return {"ok": True, "status": "ok", "imported": imported, "skipped": skipped, "source_rows": len(rows)}
    except Exception as e:
        return {"ok": False, "status": "error", "where": "convert_ig_reactions_to_leads", "error": repr(e)}
    finally:
        con.close()
# === /CONVERT IG REACTIONS TO FUNNEL LEADS V1 ===
