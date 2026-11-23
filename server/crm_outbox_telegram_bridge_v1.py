"""Content Planner callbacks for Instagram CRM outbox (same existing poller)."""
import os
import requests
from crm_instagram_outbox_v1 import approve_and_send, reject

def _allowed(cb):
    chat = str(((cb.get("message") or {}).get("chat") or {}).get("id") or "")
    user = str((cb.get("from") or {}).get("id") or "")
    allowed_chat = os.getenv("CRM_OUTBOX_ADMIN_CHAT_ID", "").strip()
    allowed_users = {x.strip() for x in os.getenv("CRM_OUTBOX_ADMIN_USER_IDS", "").split(",") if x.strip()}
    if not allowed_chat or not allowed_users or chat != allowed_chat or user not in allowed_users:
        raise PermissionError("Telegram administrator not authorized")
    return user

def handle_crm_outbox_callback(cb):
    actor = _allowed(cb)
    parts = str(cb.get("data") or "").split(":")
    if len(parts) != 3 or parts[0] != "crmout" or parts[1] not in {"y", "n"} or len(parts[2]) != 32:
        raise ValueError("invalid CRM button")
    draft_id = parts[2]
    if not all(c in "0123456789abcdef" for c in draft_id):
        raise ValueError("invalid draft identifier")
    if parts[1] == "n":
        reject(draft_id, actor)
        return {"message": "CRM: відхилено"}
    result = approve_and_send(draft_id, actor)
    return {"message": "Instagram: " + result["status"]}

def notify_admin(draft):
    """Send a review request to configured admin chat, never to a customer."""
    chat = os.getenv("CRM_OUTBOX_ADMIN_CHAT_ID", "").strip()
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
    if not chat or not token or not os.getenv("CRM_OUTBOX_ADMIN_USER_IDS"):
        raise PermissionError("Content Planner admin chat, users or token missing")
    text = ("🔔 Instagram CRM · підтвердження\n"
            "Воронка: " + str(draft["funnel_id"]) + "\n"
            "Крок: " + str(draft["step_order"]) + "\n"
            "Recipient ID: " + str(draft["recipient_id"]) + "\n\n"
            + draft["text"])
    keyboard = {"inline_keyboard": [[
        {"text": "✅ Підтвердити і відправити", "callback_data": "crmout:y:" + draft["id"]},
        {"text": "❌ Відхилити", "callback_data": "crmout:n:" + draft["id"]}
    ]]}
    r = requests.post("https://api.telegram.org/bot" + token + "/sendMessage",
        json={"chat_id": chat, "text": text, "reply_markup": keyboard}, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError("Telegram notification failed")
    return {"notified": True, "telegram_message_id": (data.get("result") or {}).get("message_id")}
