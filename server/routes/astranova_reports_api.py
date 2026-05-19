from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from datetime import date, datetime, timedelta
from calendar import monthrange
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body

from services.safety_calendar.generator import generate_safety_calendar

router = APIRouter(prefix="/api/astranova/reports", tags=["astranova-reports"])

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

        con.execute("""
        CREATE TABLE IF NOT EXISTS astranova_daily_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id TEXT NOT NULL,
            report_date TEXT NOT NULL,
            score INTEGER,
            level TEXT,
            focus TEXT,
            recommendation TEXT,
            report_text TEXT,
            debug_json TEXT,
            sent_at TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(telegram_user_id, report_date)
        )
        """)
        con.commit()


def _parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def _end_of_current_month(start: date) -> date:
    last_day = monthrange(start.year, start.month)[1]
    return date(start.year, start.month, last_day)


def _period_to_days(period: str, start: date) -> int:
    period = (period or "7").lower().strip()

    if period in ("7", "7d", "week"):
        return 7

    if period in ("15", "15d"):
        return 15

    if period in ("month", "current_month", "місяць", "month_current"):
        return (_end_of_current_month(start) - start).days + 1

    try:
        return max(1, min(int(period), 31))
    except Exception:
        return 7


def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    d = dict(row)
    if d.get("debug_json"):
        try:
            d["debug"] = json.loads(d["debug_json"])
        except Exception:
            d["debug"] = None
    d.pop("debug_json", None)
    return d


def _format_day_message(day: Dict[str, Any]) -> str:
    return (
        f"✨ <b>AstraNova · {day['date']}</b>\n\n"
        f"{day['level']}\n"
        f"Індекс: <b>{day['score']}/100</b>\n\n"
        f"🌙 <b>Фокус дня:</b>\n{day['focus']}\n\n"
        f"🧭 <b>Рекомендація:</b>\n{day['recommendation']}"
    )


def _format_calendar_summary(days: List[Dict[str, Any]], title: str) -> str:
    lines = [f"✨ <b>AstraNova · {title}</b>", ""]

    for d in days:
        ds = datetime.strptime(d["date"], "%Y-%m-%d").strftime("%d.%m")
        level = d.get("level") or ""
        emoji = "⚪️"
        if "🔴" in level:
            emoji = "🔴"
        elif "🟡" in level:
            emoji = "🟡"
        elif "🟢" in level:
            emoji = "🟢"
        elif "🟣" in level:
            emoji = "🟣"

        lines.append(f"{ds} {emoji} <b>{d['score']}/100</b> — {d['focus']}")

    lines.append("")
    lines.append("Напишіть <b>сьогодні</b>, щоб отримати детальний прогноз на день.")
    return "\n".join(lines)


def generate_and_save_reports(
    telegram_user_id: str,
    start_date: Optional[str] = None,
    period: str = "7",
) -> Dict[str, Any]:
    _init_db()

    start = _parse_date(start_date)
    period_days = _period_to_days(period, start)

    with _db() as con:
        con.row_factory = sqlite3.Row
        user = con.execute(
            "SELECT * FROM astranova_users WHERE telegram_user_id=?",
            (str(telegram_user_id),),
        ).fetchone()

        if not user:
            return {"ok": False, "error": "user_not_found"}

        user = dict(user)

    if not user.get("birth_date"):
        return {"ok": False, "error": "birth_date_missing"}

    result = generate_safety_calendar({
        "birth_date": user.get("birth_date"),
        "birth_time": user.get("birth_time"),
        "birth_place": user.get("birth_place"),
        "current_location": user.get("current_location"),
        "start_date": start.isoformat(),
        "period_days": period_days,
    })

    saved = 0

    with _db() as con:
        for day in result.get("days", []):
            report_text = _format_day_message(day)

            con.execute("""
            INSERT INTO astranova_daily_reports (
                telegram_user_id,
                report_date,
                score,
                level,
                focus,
                recommendation,
                report_text,
                debug_json,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_user_id, report_date) DO UPDATE SET
                score=excluded.score,
                level=excluded.level,
                focus=excluded.focus,
                recommendation=excluded.recommendation,
                report_text=excluded.report_text,
                debug_json=excluded.debug_json,
                updated_at=CURRENT_TIMESTAMP
            """, (
                str(telegram_user_id),
                day.get("date"),
                int(day.get("score") or 0),
                day.get("level"),
                day.get("focus"),
                day.get("recommendation"),
                report_text,
                json.dumps(day.get("debug") or {}, ensure_ascii=False),
            ))
            saved += 1

        con.commit()

    return {
        "ok": True,
        "telegram_user_id": str(telegram_user_id),
        "start_date": start.isoformat(),
        "period": period,
        "period_days": period_days,
        "saved": saved,
        "days": result.get("days", []),
    }


@router.post("/generate")
def generate_reports(payload: Dict[str, Any] = Body(...)):
    return generate_and_save_reports(
        telegram_user_id=str(payload.get("telegram_user_id") or ""),
        start_date=payload.get("start_date"),
        period=str(payload.get("period") or "7"),
    )


@router.get("/list")
def list_reports(
    telegram_user_id: str,
    start_date: Optional[str] = None,
    period: str = "7",
):
    _init_db()

    start = _parse_date(start_date)
    days = _period_to_days(period, start)
    end = start + timedelta(days=days - 1)

    with _db() as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("""
            SELECT *
            FROM astranova_daily_reports
            WHERE telegram_user_id=?
              AND report_date BETWEEN ? AND ?
            ORDER BY report_date ASC
        """, (str(telegram_user_id), start.isoformat(), end.isoformat())).fetchall()

    return {
        "ok": True,
        "telegram_user_id": str(telegram_user_id),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "count": len(rows),
        "reports": [_row_to_dict(r) for r in rows],
    }


@router.get("/today")
def today_report(telegram_user_id: str):
    _init_db()
    today = date.today().isoformat()

    with _db() as con:
        con.row_factory = sqlite3.Row
        row = con.execute("""
            SELECT *
            FROM astranova_daily_reports
            WHERE telegram_user_id=? AND report_date=?
        """, (str(telegram_user_id), today)).fetchone()

    if not row:
        generated = generate_and_save_reports(
            telegram_user_id=str(telegram_user_id),
            start_date=today,
            period="7",
        )
        if not generated.get("ok"):
            return generated

        with _db() as con:
            con.row_factory = sqlite3.Row
            row = con.execute("""
                SELECT *
                FROM astranova_daily_reports
                WHERE telegram_user_id=? AND report_date=?
            """, (str(telegram_user_id), today)).fetchone()

    return {
        "ok": True,
        "report": _row_to_dict(row) if row else None,
    }


@router.get("/summary")
def summary_report(
    telegram_user_id: str,
    period: str = "7",
    start_date: Optional[str] = None,
):
    data = list_reports(
        telegram_user_id=telegram_user_id,
        start_date=start_date,
        period=period,
    )

    if data.get("count", 0) == 0:
        generated = generate_and_save_reports(
            telegram_user_id=telegram_user_id,
            start_date=start_date,
            period=period,
        )
        if not generated.get("ok"):
            return generated

        data = list_reports(
            telegram_user_id=telegram_user_id,
            start_date=start_date,
            period=period,
        )

    title = "7 днів"
    if str(period) == "15":
        title = "15 днів"
    elif str(period).lower() in ("month", "current_month", "місяць"):
        title = "поточний місяць"

    return {
        "ok": True,
        "telegram_user_id": telegram_user_id,
        "period": period,
        "text": _format_calendar_summary(data.get("reports", []), title),
        "reports": data.get("reports", []),
    }
