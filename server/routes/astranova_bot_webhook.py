from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path
from datetime import datetime

import requests
from fastapi import APIRouter, Request
from routes.astranova_reports_api import generate_and_save_reports

router = APIRouter(tags=["astranova-bot"])

DB_PATH = Path(os.getenv("CONTENT_DB_PATH") or "data/content.db")


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


def _main_keyboard():
    return {
        "keyboard": [
            [{"text": "📅 Сьогодні"}, {"text": "📆 7 днів"}],
            [{"text": "🗓 15 днів"}, {"text": "🌙 Місяць"}],
            [{"text": "⚙️ Мій профіль"}],
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False,
    }


def _tg_send_message(chat_id: int | str, text: str, reply_markup: dict | None = None):
    token = os.getenv("ASTRANOVA_BOT_TOKEN")
    if not token:
        print("ASTRANOVA_BOT_TOKEN missing")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        r = requests.post(url, json=payload, timeout=15)
        print("ASTRANOVA sendMessage:", r.status_code, r.text[:300])
    except Exception as e:
        print("ASTRANOVA sendMessage error:", repr(e))


def _upsert_user(message: dict, source_payload: str | None = None):
    user = message.get("from") or {}
    telegram_user_id = str(user.get("id") or "")
    if not telegram_user_id:
        return None

    with _db() as con:
        con.execute("""
        INSERT INTO astranova_users (
            telegram_user_id, username, first_name, last_name,
            source_payload, onboarding_state
        )
        VALUES (?, ?, ?, ?, ?, 'awaiting_birth_date')
        ON CONFLICT(telegram_user_id) DO UPDATE SET
            username=excluded.username,
            first_name=excluded.first_name,
            last_name=excluded.last_name,
            source_payload=COALESCE(excluded.source_payload, astranova_users.source_payload),
            updated_at=CURRENT_TIMESTAMP
        """, (
            telegram_user_id,
            user.get("username"),
            user.get("first_name"),
            user.get("last_name"),
            source_payload,
        ))
        con.commit()

    return telegram_user_id


def _get_user(telegram_user_id: str):
    with _db() as con:
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT * FROM astranova_users WHERE telegram_user_id=?",
            (telegram_user_id,)
        ).fetchone()
        return dict(row) if row else None


def _set_birth_date(telegram_user_id: str, birth_date_iso: str):
    with _db() as con:
        con.execute("""
        UPDATE astranova_users
        SET birth_date=?,
            onboarding_state='awaiting_birth_time',
            updated_at=CURRENT_TIMESTAMP
        WHERE telegram_user_id=?
        """, (birth_date_iso, telegram_user_id))
        con.commit()



def _get_reports(telegram_user_id: str, period: str = "7"):
    _init_db()

    # якщо reports ще нема — генеруємо
    generate_and_save_reports(
        telegram_user_id=str(telegram_user_id),
        period=str(period),
    )

    from routes.astranova_reports_api import summary_report, today_report

    if period == "today":
        return today_report(str(telegram_user_id))

    return summary_report(
        telegram_user_id=str(telegram_user_id),
        period=str(period),
    )


def _send_today(chat_id: int | str, telegram_user_id: str):
    data = _get_reports(telegram_user_id, "today")

    report = data.get("report") if isinstance(data, dict) else None
    if not report:
        _tg_send_message(chat_id, "Поки не можу знайти прогноз на сьогодні. Спробуйте 📆 7 днів.", _main_keyboard())
        return

    text = report.get("report_text") or (
        f"✨ <b>AstraNova · сьогодні</b>\n\n"
        f"{report.get('level')}\n"
        f"Індекс: <b>{report.get('score')}/100</b>\n\n"
        f"🌙 <b>Фокус:</b>\n{report.get('focus')}\n\n"
        f"🧭 <b>Рекомендація:</b>\n{report.get('recommendation')}"
    )

    _tg_send_message(chat_id, text, _main_keyboard())


def _send_period(chat_id: int | str, telegram_user_id: str, period: str):
    data = _get_reports(telegram_user_id, period)

    if not data.get("ok"):
        _tg_send_message(
            chat_id,
            "Не можу сформувати календар. Можливо, ще не збережена дата народження.",
            _main_keyboard()
        )
        return

    text = data.get("text") or "Календар поки порожній."
    _tg_send_message(chat_id, text, _main_keyboard())


def _send_profile(chat_id: int | str, user: dict):
    text = (
        "⚙️ <b>Мій профіль AstraNova</b>\n\n"
        f"Telegram ID: <code>{user.get('telegram_user_id')}</code>\n"
        f"Імʼя: <b>{user.get('first_name') or '—'}</b>\n"
        f"Username: <b>{user.get('username') or '—'}</b>\n"
        f"Дата народження: <b>{user.get('birth_date') or '—'}</b>\n"
        f"Час народження: <b>{user.get('birth_time') or '—'}</b>\n"
        f"Місце народження: <b>{user.get('birth_place') or '—'}</b>\n"
        f"Поточне місце: <b>{user.get('current_location') or '—'}</b>\n\n"
        "Далі підключимо зміну профілю і час щоденного повідомлення."
    )
    _tg_send_message(chat_id, text, _main_keyboard())


def _parse_birth_date(text: str) -> str | None:
    text = text.strip()

    for fmt in ("%d.%m.%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            d = datetime.strptime(text, fmt).date()
            return d.isoformat()
        except ValueError:
            pass

    m = re.match(r"^(\d{1,2})[./-](\d{1,2})[./-](\d{4})$", text)
    if m:
        dd, mm, yyyy = m.groups()
        try:
            d = datetime(int(yyyy), int(mm), int(dd)).date()
            return d.isoformat()
        except ValueError:
            return None

    return None


@router.post("/webhook/astranova")
async def astranova_webhook(request: Request):
    _init_db()

    data = await request.json()
    print("ASTRANOVA UPDATE:", data)

    message = data.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    text = (message.get("text") or "").strip()

    if not chat_id:
        return {"ok": True, "reason": "no_chat_id"}

    tg_user_id = str((message.get("from") or {}).get("id") or "")
    if not tg_user_id:
        return {"ok": True, "reason": "no_user_id"}

    if text.startswith("/start"):
        payload = text.replace("/start", "", 1).strip() or None
        _upsert_user(message, payload)

        _tg_send_message(
            chat_id,
            "✨ <b>Вітаю в AstraNova</b>\n\n"
            "Я створю персональний календар безпеки на основі:\n"
            "🌙 астрологічних циклів\n"
            "🔢 нумерології\n"
            "🌀 кармології\n"
            "📍 місця перебування\n\n"
            "Для початку введіть дату народження у форматі:\n"
            "<b>ДД.ММ.РРРР</b>\n\n"
            "Наприклад: <b>12.05.1990</b>",
            _main_keyboard()
        )
        return {"ok": True}

    user = _get_user(tg_user_id)

    if not user:
        _upsert_user(message)
        _tg_send_message(
            chat_id,
            "Почнемо знайомство ✨\n\n"
            "Введіть дату народження у форматі <b>ДД.ММ.РРРР</b>."
        )
        return {"ok": True}

    state = user.get("onboarding_state") or "new"

    if state in ("new", "awaiting_birth_date") or not user.get("birth_date"):
        birth_date = _parse_birth_date(text)

        if not birth_date:
            _tg_send_message(
                chat_id,
                "Не бачу дату народження 😌\n\n"
                "Введіть, будь ласка, у форматі:\n"
                "<b>ДД.ММ.РРРР</b>\n\n"
                "Наприклад: <b>12.05.1990</b>"
            )
            return {"ok": True}

        _set_birth_date(tg_user_id, birth_date)

        generate_and_save_reports(
            telegram_user_id=tg_user_id,
            period="7",
        )

        _tg_send_message(
            chat_id,
            f"Дата народження збережена ✅\n\n"
            f"<b>{birth_date}</b>\n\n"
            "Я вже сформував перший календар на 7 днів.\n\n"
            "Оберіть дію нижче:",
            _main_keyboard()
        )
        return {"ok": True}

    if text in ("📅 Сьогодні", "сьогодні", "Сегодня", "/today"):
        _send_today(chat_id, tg_user_id)
        return {"ok": True}

    if text in ("📆 7 днів", "7", "7 днів", "/calendar", "/week"):
        _send_period(chat_id, tg_user_id, "7")
        return {"ok": True}

    if text in ("🗓 15 днів", "15", "15 днів"):
        _send_period(chat_id, tg_user_id, "15")
        return {"ok": True}

    if text in ("🌙 Місяць", "місяць", "Місяць", "month"):
        _send_period(chat_id, tg_user_id, "month")
        return {"ok": True}

    if text in ("⚙️ Мій профіль", "профіль", "/profile"):
        _send_profile(chat_id, user)
        return {"ok": True}


    _tg_send_message(
        chat_id,
        "Профіль уже створюється ✅\n\n"
        f"Дата народження: <b>{user.get('birth_date')}</b>\n\n"
        "Наступним кроком підключимо час, місце народження і генерацію календаря."
    )

    return {"ok": True}
