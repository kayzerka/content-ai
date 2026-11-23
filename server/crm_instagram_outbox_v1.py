"""Human-approved Instagram funnel outbox. No automatic sends or retries."""
import hashlib
import json
import os
import sqlite3
import urllib.request
import urllib.error
import uuid
from pathlib import Path
from datetime import datetime, timezone
import funnel_core as funnel

DB_FILE = Path(__file__).resolve().parent / "data" / "crm_instagram_outbox.sqlite3"
RENDER_URL = "https://content-ai-ps1k.onrender.com/api/meta-outbound/send-once"
SEND_TYPES = {"send_message", "send_dm", "send_free_gift", "send_cta", "send_telegram_invite"}

def _now():
    return datetime.now(timezone.utc).isoformat()

def _connect():
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_FILE), timeout=15, isolation_level=None)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=15000")
    c.execute("""CREATE TABLE IF NOT EXISTS instagram_outbox(
        id TEXT PRIMARY KEY, funnel_id INTEGER NOT NULL, contact_id INTEGER NOT NULL,
        recipient_id TEXT NOT NULL, step_order INTEGER NOT NULL, text TEXT NOT NULL,
        text_hash TEXT NOT NULL, status TEXT NOT NULL, request_id TEXT UNIQUE NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        approved_by TEXT, meta_message_id TEXT, error TEXT,
        UNIQUE(funnel_id, contact_id, step_order)
    )""")
    return c

def _row(c, draft_id):
    r = c.execute("SELECT * FROM instagram_outbox WHERE id=?", (draft_id,)).fetchone()
    return dict(r) if r else None

def _eligible(recipient):
    allowed = {s.strip() for s in os.getenv("META_OUTBOUND_ALLOWED_RECIPIENTS", "").split(",") if s.strip()}
    # Render has its own independent recipient allowlist; local must fail closed too.
    return recipient.isdigit() and recipient in allowed

def _step_text(step):
    cfg = step.get("config") or {}
    text = (str(cfg.get("text") or cfg.get("title") or "") +
            ("\n" + str(cfg["url"]) if cfg.get("url") else "")).strip()
    if not text or len(text) > 1000:
        raise ValueError("message text empty or longer than 1000 characters")
    return text

def create_draft(funnel_id, external_user_id):
    if os.getenv("CRM_INSTAGRAM_OUTBOX_ENABLED") != "1":
        raise PermissionError("Instagram outbox disabled")
    contact = funnel.get_contact_by_external(int(funnel_id), "instagram", str(external_user_id))
    if not contact:
        raise ValueError("funnel contact not found")
    recipient = str(contact["external_user_id"])
    if not _eligible(recipient):
        raise PermissionError("recipient not on verified allowlist")
    step_order = int(contact.get("current_step") or 1)
    step = funnel.get_step(int(funnel_id), step_order)
    if not step or step["step_type"] not in SEND_TYPES:
        raise ValueError("current step is not a supported Instagram message step")
    cfg = step.get("config") or {}
    if (cfg.get("delivery") or cfg.get("send_via") or "instagram") != "instagram":
        raise ValueError("step delivery is not Instagram")
    message = _step_text(step)
    digest = hashlib.sha256(message.encode()).hexdigest()
    c = _connect()
    try:
        c.execute("BEGIN IMMEDIATE")
        prior = c.execute("SELECT * FROM instagram_outbox WHERE funnel_id=? AND contact_id=? AND step_order=?",
                          (int(funnel_id), contact["id"], step_order)).fetchone()
        if prior:
            result = dict(prior)
            if result["text_hash"] != digest:
                raise ValueError("existing draft differs; manual reconciliation required")
            c.commit()
            return result
        draft_id = uuid.uuid4().hex
        request_id = "crmig_" + draft_id
        now = _now()
        c.execute("""INSERT INTO instagram_outbox
            (id,funnel_id,contact_id,recipient_id,step_order,text,text_hash,status,request_id,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,'pending_approval',?,?,?)""",
            (draft_id, int(funnel_id), contact["id"], recipient, step_order, message, digest, request_id, now, now))
        result = _row(c, draft_id)
        c.commit()
        return result
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def list_drafts():
    c = _connect()
    try:
        return [dict(x) for x in c.execute("SELECT * FROM instagram_outbox ORDER BY created_at DESC LIMIT 100")]
    finally:
        c.close()

def reject(draft_id, actor):
    c = _connect()
    try:
        c.execute("BEGIN IMMEDIATE")
        n = c.execute("UPDATE instagram_outbox SET status='rejected', approved_by=?,updated_at=? WHERE id=? AND status='pending_approval'",
                      (str(actor), _now(), draft_id)).rowcount
        if n != 1:
            raise ValueError("already decided or not found")
        c.commit()
        return {"status": "rejected", "sent": False}
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()

def approve_and_send(draft_id, actor):
    """One-way claim BEFORE network call. Unknown results are never retried."""
    if os.getenv("CRM_INSTAGRAM_OUTBOX_ENABLED") != "1":
        raise PermissionError("Instagram outbox disabled")
    token = os.getenv("META_OUTBOUND_TOKEN", "").strip()
    if not token:
        raise PermissionError("META_OUTBOUND_TOKEN missing on Mac")
    c = _connect()
    try:
        c.execute("BEGIN IMMEDIATE")
        row = _row(c, draft_id)
        if not row or row["status"] != "pending_approval":
            raise ValueError("draft already decided or missing")
        if not _eligible(row["recipient_id"]):
            raise PermissionError("recipient no longer allowed")
        contact = funnel.get_contact_by_external(row["funnel_id"], "instagram", row["recipient_id"])
        if not contact or contact["id"] != row["contact_id"] or int(contact["current_step"]) != row["step_order"]:
            raise ValueError("contact changed step or identity")
        step = funnel.get_step(row["funnel_id"], row["step_order"])
        if not step or step["step_type"] not in SEND_TYPES or hashlib.sha256(_step_text(step).encode()).hexdigest() != row["text_hash"]:
            raise ValueError("step or message changed")
        if c.execute("UPDATE instagram_outbox SET status='sending',approved_by=?,updated_at=? WHERE id=? AND status='pending_approval'",
                     (str(actor), _now(), draft_id)).rowcount != 1:
            raise ValueError("claim failed")
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()
    body = json.dumps({"recipient_id": row["recipient_id"], "text": row["text"],
                       "request_id": row["request_id"], "confirmed": True}, ensure_ascii=False).encode()
    req = urllib.request.Request(RENDER_URL, data=body, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    status, mid, err = "unknown", None, "ambiguous network result"
    try:
        with urllib.request.urlopen(req, timeout=35) as resp:
            result = json.loads(resp.read().decode())
        if result.get("ok") and result.get("status") == "accepted":
            status = "accepted"
            mid = str((result.get("result") or {}).get("message_id") or "")
        elif result.get("status") == "rejected":
            status, err = "rejected", "Render rejected request"
    except urllib.error.HTTPError as exc:
        # A definite HTTP error still might follow upstream send: never retry automatically.
        err = "Render HTTP " + str(exc.code)
    except Exception as exc:
        err = "Render outcome uncertain: " + type(exc).__name__
    c = _connect()
    try:
        c.execute("BEGIN IMMEDIATE")
        c.execute("UPDATE instagram_outbox SET status=?,meta_message_id=?,error=?,updated_at=? WHERE id=? AND status='sending'",
                  (status, mid, err if status != "accepted" else None, _now(), draft_id))
        c.commit()
    finally:
        c.close()
    if status == "accepted":
        # Conditional advance, never overwrite a contact that moved concurrently.
        fc = funnel.db()
        try:
            with fc:
                changed = fc.execute("""UPDATE funnel_contacts SET current_step=?
                    WHERE id=? AND funnel_id=? AND platform='instagram' AND external_user_id=? AND current_step=?""",
                    (row["step_order"]+1, row["contact_id"], row["funnel_id"],
                     row["recipient_id"], row["step_order"])).rowcount
            if changed:
                funnel.log_event(row["funnel_id"], row["contact_id"], "instagram_accepted",
                                 {"outbox_id": draft_id, "meta_message_id": mid, "step_order": row["step_order"]})
            else:
                err = "accepted but contact step changed; reconcile manually"
        finally:
            fc.close()
    return {"status": status, "meta_message_id": mid, "warning": err if status == "accepted" else None, "sent": status == "accepted"}
