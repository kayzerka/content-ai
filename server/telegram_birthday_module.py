import os
import sqlite3
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

import requests
from PIL import Image, ImageDraw, ImageFont

DB_PATH = "db/telegram.sqlite"
TEMPLATE_DIR = Path("static/birthday_templates")
GENERATED_DIR = Path("data/generated_birthday_cards")


def _db():
    Path("db").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> int:
    return int(time.time())


def init_telegram_birthday_tables():
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)

    con = _db()

    con.execute("""
        CREATE TABLE IF NOT EXISTS telegram_birthday_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT UNIQUE NOT NULL,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            birthday_date TEXT,
            discount_percent INTEGER DEFAULT 15,
            discount_code TEXT,
            birthday_last_sent_year INTEGER,
            template_image TEXT,
            created_at INTEGER,
            updated_at INTEGER
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS telegram_birthday_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            enabled INTEGER DEFAULT 1,
            auto_run_enabled INTEGER DEFAULT 0,
            auto_run_hour INTEGER DEFAULT 9,
            auto_run_minute INTEGER DEFAULT 0,
            template_image TEXT,
            message_template TEXT,
            caption_template TEXT,
            services_template TEXT,
            font_message_family TEXT,
            font_message_size INTEGER DEFAULT 22,
            font_message_color TEXT DEFAULT '#463732',
            font_discount_family TEXT,
            font_discount_size INTEGER DEFAULT 120,
            font_discount_color TEXT DEFAULT '#a55d63',
            font_services_family TEXT,
            font_services_size INTEGER DEFAULT 26,
            font_services_color TEXT DEFAULT '#3a2d28',
            font_date_family TEXT,
            font_date_size INTEGER DEFAULT 34,
            font_date_color TEXT DEFAULT '#a55d63',
            pos_message_x REAL DEFAULT 0.040,
            pos_message_y REAL DEFAULT 0.300,
            pos_discount_x REAL DEFAULT 0.565,
            pos_discount_y REAL DEFAULT 0.205,
            pos_services_x REAL DEFAULT 0.565,
            pos_services_y REAL DEFAULT 0.505,
            pos_date_x REAL DEFAULT 0.685,
            pos_date_y REAL DEFAULT 0.846,
            last_auto_run_date TEXT,
            last_run_at INTEGER,
            last_run_sent INTEGER DEFAULT 0,
            last_run_errors INTEGER DEFAULT 0,
            updated_at INTEGER
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS telegram_birthday_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id TEXT,
            contact_name TEXT,
            birthday_date TEXT,
            template_image TEXT,
            discount_percent INTEGER,
            discount_code TEXT,
            status TEXT,
            error TEXT,
            sent_at INTEGER
        )
    """)

    default_message = """🎉 {first_name}, вітаємо з Днем народження!

Нехай цей новий рік життя принесе більше легкості, радості та внутрішньої опори 💛

А від нас — маленький подарунок: персональна знижка {discount_percent}% на сесію / консультацію.

🎁 Ваш промокод: {discount_code}

Промокод діє до {valid_until}."""

    default_caption = "🎁 Ваш подарунок до Дня народження"

    default_services = """♡ Навчання БВ
♡ 5 сеансів БВ
♡ Сеанс квантової регресії
♡ Сеанс Божого потоку
♡ Обмін енергіями
♡ Родові програми
♡ Курс «Етика сили»"""

    try:
        con.execute("ALTER TABLE telegram_birthday_settings ADD COLUMN services_template TEXT")
    except Exception:
        pass

    for _col_sql in [
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_message_family TEXT",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_message_size INTEGER DEFAULT 22",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_message_color TEXT DEFAULT '#463732'",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_discount_family TEXT",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_discount_size INTEGER DEFAULT 120",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_discount_color TEXT DEFAULT '#a55d63'",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_services_family TEXT",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_services_size INTEGER DEFAULT 26",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_services_color TEXT DEFAULT '#3a2d28'",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_date_family TEXT",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_date_size INTEGER DEFAULT 34",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN font_date_color TEXT DEFAULT '#a55d63'",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN pos_message_x REAL DEFAULT 0.040",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN pos_message_y REAL DEFAULT 0.300",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN pos_discount_x REAL DEFAULT 0.565",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN pos_discount_y REAL DEFAULT 0.205",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN pos_services_x REAL DEFAULT 0.565",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN pos_services_y REAL DEFAULT 0.505",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN pos_date_x REAL DEFAULT 0.685",
        "ALTER TABLE telegram_birthday_settings ADD COLUMN pos_date_y REAL DEFAULT 0.846",
    ]:
        try:
            con.execute(_col_sql)
        except Exception:
            pass

    con.execute("""
        INSERT OR IGNORE INTO telegram_birthday_settings
        (
            id, enabled, auto_run_enabled, auto_run_hour, auto_run_minute,
            message_template, caption_template, services_template,
            font_message_family, font_message_size, font_message_color,
            font_discount_family, font_discount_size, font_discount_color,
            font_services_family, font_services_size, font_services_color,
            font_date_family, font_date_size, font_date_color,
            updated_at
        )
        VALUES (
            1, 1, 0, 9, 0,
            ?, ?, ?,
            'Avenir', 22, '#463732',
            'Georgia', 120, '#a55d63',
            'Georgia', 26, '#3a2d28',
            'Georgia', 34, '#a55d63',
            ?
        )
    """, (default_message, default_caption, default_services, _now()))

    con.commit()
    con.close()


def get_settings() -> Dict[str, Any]:
    init_telegram_birthday_tables()
    con = _db()
    row = con.execute("SELECT * FROM telegram_birthday_settings WHERE id = 1").fetchone()
    con.close()
    return dict(row) if row else {}


def save_settings(payload: Dict[str, Any]) -> Dict[str, Any]:
    init_telegram_birthday_tables()
    current = get_settings()

    enabled = int(payload.get("enabled", current.get("enabled", 1)) or 0)
    auto_run_enabled = int(payload.get("auto_run_enabled", current.get("auto_run_enabled", 0)) or 0)
    auto_run_hour = int(payload.get("auto_run_hour", current.get("auto_run_hour", 9)) or 9)
    auto_run_minute = int(payload.get("auto_run_minute", current.get("auto_run_minute", 0)) or 0)

    auto_run_hour = max(0, min(23, auto_run_hour))
    auto_run_minute = max(0, min(59, auto_run_minute))

    con = _db()
    con.execute("""
        UPDATE telegram_birthday_settings
        SET enabled = ?,
            auto_run_enabled = ?,
            auto_run_hour = ?,
            auto_run_minute = ?,
            template_image = ?,
            message_template = ?,
            caption_template = ?,
            services_template = ?,
            font_message_family = ?,
            font_message_size = ?,
            font_message_color = ?,
            font_discount_family = ?,
            font_discount_size = ?,
            font_discount_color = ?,
            font_services_family = ?,
            font_services_size = ?,
            font_services_color = ?,
            font_date_family = ?,
            font_date_size = ?,
            font_date_color = ?,
            pos_message_x = ?,
            pos_message_y = ?,
            pos_discount_x = ?,
            pos_discount_y = ?,
            pos_services_x = ?,
            pos_services_y = ?,
            pos_date_x = ?,
            pos_date_y = ?,
            updated_at = ?
        WHERE id = 1
    """, (
        enabled,
        auto_run_enabled,
        auto_run_hour,
        auto_run_minute,
        payload.get("template_image", current.get("template_image")),
        payload.get("message_template", current.get("message_template")),
        payload.get("caption_template", current.get("caption_template")),
        payload.get("services_template", current.get("services_template")),
        payload.get("font_message_family", current.get("font_message_family") or "Avenir"),
        int(payload.get("font_message_size", current.get("font_message_size") or 22) or 22),
        payload.get("font_message_color", current.get("font_message_color") or "#463732"),
        payload.get("font_discount_family", current.get("font_discount_family") or "Georgia"),
        int(payload.get("font_discount_size", current.get("font_discount_size") or 120) or 120),
        payload.get("font_discount_color", current.get("font_discount_color") or "#a55d63"),
        payload.get("font_services_family", current.get("font_services_family") or "Georgia"),
        int(payload.get("font_services_size", current.get("font_services_size") or 26) or 26),
        payload.get("font_services_color", current.get("font_services_color") or "#3a2d28"),
        payload.get("font_date_family", current.get("font_date_family") or "Georgia"),
        int(payload.get("font_date_size", current.get("font_date_size") or 34) or 34),
        payload.get("font_date_color", current.get("font_date_color") or "#a55d63"),
        float(payload.get("pos_message_x", current.get("pos_message_x") or 0.040) or 0.040),
        float(payload.get("pos_message_y", current.get("pos_message_y") or 0.300) or 0.300),
        float(payload.get("pos_discount_x", current.get("pos_discount_x") or 0.565) or 0.565),
        float(payload.get("pos_discount_y", current.get("pos_discount_y") or 0.205) or 0.205),
        float(payload.get("pos_services_x", current.get("pos_services_x") or 0.565) or 0.565),
        float(payload.get("pos_services_y", current.get("pos_services_y") or 0.505) or 0.505),
        float(payload.get("pos_date_x", current.get("pos_date_x") or 0.685) or 0.685),
        float(payload.get("pos_date_y", current.get("pos_date_y") or 0.846) or 0.846),
        _now(),
    ))
    con.commit()
    con.close()

    return {"ok": True, "settings": get_settings()}


def list_templates() -> Dict[str, Any]:
    init_telegram_birthday_tables()
    items = []
    for p in TEMPLATE_DIR.glob("*"):
        if p.suffix.lower() in [".png", ".jpg", ".jpeg", ".webp"]:
            items.append({
                "name": p.name,
                "path": str(p),
                "url": "/" + str(p).replace("\\", "/"),
            })
    return {"ok": True, "items": items, "count": len(items)}


def upsert_birthday_contact(payload: Dict[str, Any]) -> Dict[str, Any]:
    init_telegram_birthday_tables()

    chat_id = str(payload.get("chat_id") or "").strip()
    birthday_date = str(payload.get("birthday_date") or "").strip()

    if not chat_id:
        return {"ok": False, "error": "chat_id_required"}
    if not birthday_date:
        return {"ok": False, "error": "birthday_date_required"}

    con = _db()
    con.execute("""
        INSERT INTO telegram_birthday_contacts
        (chat_id, username, first_name, last_name, birthday_date, discount_percent, discount_code, template_image, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            username = excluded.username,
            first_name = excluded.first_name,
            last_name = excluded.last_name,
            birthday_date = excluded.birthday_date,
            discount_percent = excluded.discount_percent,
            discount_code = excluded.discount_code,
            template_image = excluded.template_image,
            updated_at = excluded.updated_at
    """, (
        chat_id,
        str(payload.get("username") or "").strip(),
        str(payload.get("first_name") or "").strip(),
        str(payload.get("last_name") or "").strip(),
        birthday_date,
        int(payload.get("discount_percent") or 15),
        str(payload.get("discount_code") or "BDAY15").strip(),
        str(payload.get("template_image") or "").strip(),
        _now(),
        _now(),
    ))
    con.commit()
    con.close()

    return {"ok": True, "chat_id": chat_id}


def list_contacts() -> Dict[str, Any]:
    init_telegram_birthday_tables()
    con = _db()
    rows = con.execute("""
        SELECT *
        FROM telegram_birthday_contacts
        ORDER BY updated_at DESC, id DESC
    """).fetchall()
    con.close()
    return {"ok": True, "items": [dict(r) for r in rows], "count": len(rows)}


def list_logs(limit: int = 100) -> Dict[str, Any]:
    init_telegram_birthday_tables()
    con = _db()
    rows = con.execute("""
        SELECT *
        FROM telegram_birthday_logs
        ORDER BY id DESC
        LIMIT ?
    """, (int(limit or 100),)).fetchall()
    con.close()
    return {"ok": True, "items": [dict(r) for r in rows], "count": len(rows)}


def _format_template(template: str, row: Dict[str, Any]) -> str:
    valid_until = (date.today() + timedelta(days=7)).strftime("%d.%m.%Y")
    first_name = row.get("first_name") or "вітаємо"
    discount_percent = row.get("discount_percent") or 15
    discount_code = row.get("discount_code") or f"BDAY{discount_percent}"

    data = {
        "first_name": first_name,
        "last_name": row.get("last_name") or "",
        "username": row.get("username") or "",
        "discount_percent": discount_percent,
        "discount_code": discount_code,
        "valid_until": valid_until,
        "birthday_date": row.get("birthday_date") or "",
    }

    try:
        return (template or "").format(**data)
    except Exception:
        return template or ""


def build_message(row: Dict[str, Any]) -> str:
    settings = get_settings()
    return _format_template(settings.get("message_template") or "", row)


def build_caption(row: Dict[str, Any]) -> str:
    settings = get_settings()
    return _format_template(settings.get("caption_template") or "", row)



def _hex_to_rgb(value: str, fallback=(70, 55, 50)):
    try:
        v = str(value or "").strip()
        if v.startswith("#"):
            v = v[1:]
        if len(v) == 3:
            v = "".join([c * 2 for c in v])
        if len(v) != 6:
            return fallback
        return tuple(int(v[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return fallback


def _font_from_family(family: str, size: int):
    family = (family or "").lower().strip()
    candidates = []

    if "script" in family or "chancery" in family or "snell" in family:
        candidates += [
            "/System/Library/Fonts/Supplemental/Apple Chancery.ttf",
            "/System/Library/Fonts/Supplemental/Snell Roundhand.ttf",
        ]

    if "georgia" in family or "serif" in family:
        candidates += [
            "/System/Library/Fonts/Supplemental/Georgia.ttf",
            "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ]

    if "avenir" in family or "sans" in family or "arial" in family:
        candidates += [
            "/System/Library/Fonts/Supplemental/Avenir Next.ttc",
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    candidates += [
        "/System/Library/Fonts/Supplemental/Georgia.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ]

    for c in candidates:
        if Path(c).exists():
            try:
                return ImageFont.truetype(c, int(size))
            except Exception:
                pass
    return ImageFont.load_default()

def _find_font(size: int):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> str:
    words = str(text or "").split()
    lines = []
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        try:
            width = draw.textbbox((0, 0), test, font=font)[2]
        except Exception:
            width = draw.textlength(test, font=font)
        if width <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return "\n".join(lines)


def generate_birthday_card(row: Dict[str, Any]) -> Optional[str]:
    settings = get_settings()
    template_name = row.get("template_image") or settings.get("template_image")

    if not template_name:
        return None

    template_name = Path(str(template_name)).name
    template_path = TEMPLATE_DIR / template_name

    if not template_path.exists():
        return None

    img = Image.open(template_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    w, h = img.size
    font_big = _find_font(max(28, int(w * 0.045)))
    font_mid = _find_font(max(22, int(w * 0.032)))
    font_small = _find_font(max(18, int(w * 0.024)))

    name = row.get("first_name") or ""
    discount = row.get("discount_percent") or 15
    code = row.get("discount_code") or f"BDAY{discount}"

    color = (126, 74, 62)

    settings = get_settings()

    # 1) ліва верхня частина — редагований привітальний текст
    left_text = build_message(row)
    left_text = left_text.replace("🎉", "").replace("💛", "").replace("🎁", "").strip()

    left_font = _font_from_family(
        settings.get("font_message_family") or "Avenir",
        int(settings.get("font_message_size") or 22)
    )
    left_wrapped = _wrap_text(draw, left_text, left_font, int(w * 0.255))
    draw.multiline_text(
        (int(w * float(settings.get('pos_message_x') or 0.040)), int(h * float(settings.get('pos_message_y') or 0.300))),
        left_wrapped,
        font=left_font,
        fill=_hex_to_rgb(settings.get("font_message_color"), (70, 55, 50)),
        spacing=max(8, int(h * 0.010))
    )

    # 2) права верхня частина — велика знижка
    discount_font = _font_from_family(
        settings.get("font_discount_family") or "Georgia",
        int(settings.get("font_discount_size") or max(110, int(w * 0.088)))
    )
    draw.text(
        (int(w * float(settings.get('pos_discount_x') or 0.565)), int(h * float(settings.get('pos_discount_y') or 0.205))),
        f"{discount}%",
        font=discount_font,
        fill=_hex_to_rgb(settings.get("font_discount_color"), (165, 93, 99))
    )

    # 3) перелік послуг — переносимо вниз під подарунковий блок
    services_text = settings.get("services_template") or ""
    services_text = _format_template(services_text, row)
    service_lines = [x.strip() for x in services_text.splitlines() if x.strip()]
    services_text = "\n".join(("• " + x.lstrip("•♡◎☼◌♧☆📖 ").strip()) for x in service_lines)

    services_font = _font_from_family(
        settings.get("font_services_family") or "Georgia",
        int(settings.get("font_services_size") or 20)
    )
    draw.multiline_text(
        (int(w * float(settings.get('pos_services_x') or 0.565)), int(h * float(settings.get('pos_services_y') or 0.505))),
        services_text,
        font=services_font,
        fill=_hex_to_rgb(settings.get("font_services_color"), (58, 45, 40)),
        spacing=max(7, int(h * 0.009))
    )

    # 4) дата в нижній блок після слова "до"
    valid_until = (date.today() + timedelta(days=7)).strftime("%d.%m")
    date_font = _font_from_family(
        settings.get("font_date_family") or "Georgia",
        int(settings.get("font_date_size") or 34)
    )
    draw.text(
        (int(w * float(settings.get('pos_date_x') or 0.685)), int(h * float(settings.get('pos_date_y') or 0.846))),
        valid_until,
        font=date_font,
        fill=_hex_to_rgb(settings.get("font_date_color"), (165, 93, 99))
    )

    out = GENERATED_DIR / f"birthday_{row.get('chat_id')}_{date.today().year}.jpg"
    img.save(out, "JPEG", quality=95)
    return str(out)


def _get_bot_token(purpose: str = "planner") -> Optional[str]:
    if purpose == "contact":
        keys = [
            "BIRTHDAY_TELEGRAM_BOT_TOKEN",
            "DASHA_TELEGRAM_BOT_TOKEN",
            "CLIENT_TELEGRAM_BOT_TOKEN",
        ]
    else:
        keys = [
            "TELEGRAM_BOT_TOKEN",
            "BOT_TOKEN",
            "TG_BOT_TOKEN",
            "TELEGRAM_TOKEN",
        ]

    for key in keys:
        v = os.getenv(key)
        if v:
            return v
    return None


def send_telegram_photo(chat_id: str, photo_path: str, caption: str = "", purpose: str = "planner") -> Dict[str, Any]:
    token = _get_bot_token(purpose)
    if not token:
        return {"ok": False, "error": "telegram_token_not_found"}

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    with open(photo_path, "rb") as f:
        r = requests.post(
            url,
            data={
                "chat_id": str(chat_id),
                "caption": caption or "",
            },
            files={"photo": f},
            timeout=30,
        )
    try:
        return r.json()
    except Exception:
        return {"ok": False, "status_code": r.status_code, "text": r.text}


def send_telegram_text(chat_id: str, text: str, purpose: str = "planner") -> Dict[str, Any]:
    token = _get_bot_token(purpose)
    if not token:
        return {"ok": False, "error": "telegram_token_not_found"}

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    r = requests.post(
        url,
        json={
            "chat_id": str(chat_id),
            "text": text,
        },
        timeout=30,
    )
    try:
        return r.json()
    except Exception:
        return {"ok": False, "status_code": r.status_code, "text": r.text}


def _log(row: Dict[str, Any], status: str, error: str = ""):
    con = _db()
    con.execute("""
        INSERT INTO telegram_birthday_logs
        (chat_id, contact_name, birthday_date, template_image, discount_percent, discount_code, status, error, sent_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(row.get("chat_id") or ""),
        str(row.get("first_name") or ""),
        str(row.get("birthday_date") or ""),
        str(row.get("template_image") or ""),
        int(row.get("discount_percent") or 15),
        str(row.get("discount_code") or ""),
        status,
        error,
        _now(),
    ))
    con.commit()
    con.close()


def _mark_sent(chat_id: str):
    con = _db()
    con.execute("""
        UPDATE telegram_birthday_contacts
        SET birthday_last_sent_year = ?,
            updated_at = ?
        WHERE chat_id = ?
    """, (date.today().year, _now(), str(chat_id)))
    con.commit()
    con.close()


def get_due_contacts() -> List[Dict[str, Any]]:
    init_telegram_birthday_tables()
    today = date.today()
    mmdd = today.strftime("%m-%d")
    year = today.year

    con = _db()
    rows = con.execute("""
        SELECT *
        FROM telegram_birthday_contacts
        WHERE birthday_date IS NOT NULL
          AND substr(birthday_date, 6, 5) = ?
          AND (
                birthday_last_sent_year IS NULL
                OR birthday_last_sent_year != ?
          )
    """, (mmdd, year)).fetchall()
    con.close()
    return [dict(r) for r in rows]


def run_birthday_sender(force_chat_id: Optional[str] = None, purpose: str = "planner") -> Dict[str, Any]:
    init_telegram_birthday_tables()
    settings = get_settings()

    if not int(settings.get("enabled", 1)):
        return {"ok": False, "status": "disabled"}

    if force_chat_id:
        con = _db()
        rows = con.execute("SELECT * FROM telegram_birthday_contacts WHERE chat_id = ?", (str(force_chat_id),)).fetchall()
        con.close()
        contacts = [dict(r) for r in rows]
    else:
        contacts = get_due_contacts()

    sent = 0
    errors = []

    for row in contacts:
        chat_id = str(row.get("chat_id") or "")
        try:
            img = generate_birthday_card(row)
            caption = build_caption(row)
            msg = build_message(row)

            if img:
                res = send_telegram_photo(chat_id, img, caption=caption, purpose=purpose)
            else:
                res = send_telegram_text(chat_id, msg, purpose=purpose)

            if not isinstance(res, dict) or not res.get("ok"):
                raise RuntimeError(str(res))

            if not force_chat_id:
                _mark_sent(chat_id)

            _log(row, "sent", "")
            sent += 1

        except Exception as e:
            err = str(e)
            errors.append({"chat_id": chat_id, "error": err})
            _log(row, "error", err)

    con = _db()
    con.execute("""
        UPDATE telegram_birthday_settings
        SET last_run_at = ?,
            last_run_sent = ?,
            last_run_errors = ?,
            updated_at = ?
        WHERE id = 1
    """, (_now(), sent, len(errors), _now()))
    con.commit()
    con.close()

    return {
        "ok": True,
        "checked": len(contacts),
        "sent": sent,
        "errors": errors,
    }


def maybe_auto_run_birthday_sender() -> Dict[str, Any]:
    init_telegram_birthday_tables()
    settings = get_settings()

    if not int(settings.get("enabled", 1)):
        return {"ok": True, "status": "disabled"}

    if not int(settings.get("auto_run_enabled", 0)):
        return {"ok": True, "status": "auto_disabled"}

    today = date.today().isoformat()
    if settings.get("last_auto_run_date") == today:
        return {"ok": True, "status": "already_ran_today"}

    now_struct = time.localtime()
    hour = int(settings.get("auto_run_hour") or 9)
    minute = int(settings.get("auto_run_minute") or 0)

    if (now_struct.tm_hour, now_struct.tm_min) < (hour, minute):
        return {"ok": True, "status": "not_time_yet"}

    result = run_birthday_sender(purpose="planner")

    con = _db()
    con.execute("""
        UPDATE telegram_birthday_settings
        SET last_auto_run_date = ?,
            updated_at = ?
        WHERE id = 1
    """, (today, _now()))
    con.commit()
    con.close()

    result["auto"] = True
    return result


def export_birthday_contacts_backup() -> Dict[str, Any]:
    init_telegram_birthday_tables()
    con = _db()
    contacts = [dict(r) for r in con.execute("SELECT * FROM telegram_birthday_contacts ORDER BY id").fetchall()]
    settings = get_settings()
    con.close()

    payload = {
        "ok": True,
        "type": "telegram_birthday_contacts_backup",
        "created_at": _now(),
        "settings": settings,
        "contacts": contacts,
        "count": len(contacts),
    }

    backup_dir = Path("backups")
    backup_dir.mkdir(parents=True, exist_ok=True)
    out = backup_dir / "birthday-contacts-latest.json"
    import json
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": True, "saved_to": str(out), "count": len(contacts), "backup": payload}


def restore_birthday_contacts_backup() -> Dict[str, Any]:
    init_telegram_birthday_tables()
    import json
    backup_file = Path("backups/birthday-contacts-latest.json")
    if not backup_file.exists():
        return {"ok": False, "error": "birthday_contacts_backup_not_found", "path": str(backup_file)}

    data = json.loads(backup_file.read_text(encoding="utf-8"))
    contacts = data.get("contacts") or []
    settings = data.get("settings") or {}

    con = _db()

    restored = 0
    for c in contacts:
        chat_id = str(c.get("chat_id") or "").strip()
        if not chat_id:
            continue
        con.execute("""
            INSERT INTO telegram_birthday_contacts
            (chat_id, username, first_name, last_name, birthday_date, discount_percent, discount_code, birthday_last_sent_year, template_image, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET
                username = excluded.username,
                first_name = excluded.first_name,
                last_name = excluded.last_name,
                birthday_date = excluded.birthday_date,
                discount_percent = excluded.discount_percent,
                discount_code = excluded.discount_code,
                birthday_last_sent_year = excluded.birthday_last_sent_year,
                template_image = excluded.template_image,
                updated_at = excluded.updated_at
        """, (
            chat_id,
            c.get("username") or "",
            c.get("first_name") or "",
            c.get("last_name") or "",
            c.get("birthday_date") or "",
            int(c.get("discount_percent") or 15),
            c.get("discount_code") or "BDAY15",
            c.get("birthday_last_sent_year"),
            c.get("template_image") or "",
            int(c.get("created_at") or _now()),
            _now(),
        ))
        restored += 1

    # restore settings fields without overwriting run stats too aggressively
    if settings:
        allowed = [
            "enabled", "auto_run_enabled", "auto_run_hour", "auto_run_minute",
            "template_image", "message_template", "caption_template", "services_template",
            "font_message_family", "font_message_size", "font_message_color",
            "font_discount_family", "font_discount_size", "font_discount_color",
            "font_services_family", "font_services_size", "font_services_color",
            "font_date_family", "font_date_size", "font_date_color",
        ]
        sets = []
        vals = []
        for k in allowed:
            if k in settings:
                sets.append(f"{k} = ?")
                vals.append(settings.get(k))
        if sets:
            vals.append(_now())
            con.execute(f"UPDATE telegram_birthday_settings SET {', '.join(sets)}, updated_at = ? WHERE id = 1", vals)

    con.commit()
    con.close()
    return {"ok": True, "restored": restored, "from": str(backup_file)}
