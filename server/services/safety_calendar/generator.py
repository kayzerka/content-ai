from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Dict, List


def _parse_date(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def _digit_sum(n: int) -> int:
    while n > 9:
        n = sum(int(x) for x in str(n))
    return n


def numerology_score(birth_date: date, target_date: date) -> Dict[str, Any]:
    life_path = _digit_sum(
        birth_date.year + birth_date.month + birth_date.day
    )
    day_code = _digit_sum(
        target_date.year + target_date.month + target_date.day + life_path
    )

    base = 50 + (day_code - 5) * 5
    score = max(10, min(90, base))

    meanings = {
        1: "нові рішення, ініціатива",
        2: "партнерство, емоції, домовленості",
        3: "спілкування, творчість, публічність",
        4: "структура, документи, дисципліна",
        5: "зміни, дорога, нестабільність",
        6: "сімʼя, відповідальність, турбота",
        7: "аналіз, інтуїція, внутрішня тиша",
        8: "фінанси, влада, контроль",
        9: "завершення, очищення, відпускання",
    }

    return {
        "life_path": life_path,
        "day_code": day_code,
        "score": score,
        "theme": meanings.get(day_code, "нейтральний день"),
    }


def karmology_score(birth_date: date, target_date: date) -> Dict[str, Any]:
    raw = (
        birth_date.day * 3
        + birth_date.month * 5
        + target_date.day * 7
        + target_date.month
    ) % 100

    tension = raw % 9 + 1
    score = 85 - tension * 6
    score = max(20, min(90, score))

    if tension <= 3:
        lesson = "день мʼякий, добре для спокійних рішень"
    elif tension <= 6:
        lesson = "день показує старі реакції, важливо не діяти автоматично"
    else:
        lesson = "можливі кармічні тригери: контроль, страх, образа або поспіх"

    return {
        "tension": tension,
        "score": score,
        "lesson": lesson,
    }


def moon_like_cycle_score(target_date: date) -> Dict[str, Any]:
    # MVP-імітація місячного циклу без Swiss Ephemeris.
    # Потім замінимо на реальну астрологію.
    known_new_moon = date(2026, 5, 16)
    cycle_day = (target_date - known_new_moon).days % 29

    if cycle_day in (0, 1, 2):
        score = 58
        phase = "новий цикл"
        advice = "не поспішати, краще формувати намір"
    elif 3 <= cycle_day <= 10:
        score = 72
        phase = "ріст"
        advice = "добре запускати поступові дії"
    elif 11 <= cycle_day <= 17:
        score = 62
        phase = "пік емоцій"
        advice = "не перегрівати конфлікти"
    elif 18 <= cycle_day <= 24:
        score = 66
        phase = "спад"
        advice = "добре завершувати і чистити зайве"
    else:
        score = 54
        phase = "темний період циклу"
        advice = "більше тиші, менше різких рішень"

    return {
        "cycle_day": cycle_day,
        "score": score,
        "phase": phase,
        "advice": advice,
    }


def build_recommendation(total_score: int, parts: Dict[str, Any]) -> Dict[str, str]:
    if total_score < 35:
        level = "🔴 напружений день"
        summary = "День потребує максимальної обережності."
    elif total_score < 60:
        level = "🟡 день обережності"
        summary = "День нормальний, але рішення краще перевіряти."
    elif total_score < 80:
        level = "🟢 стабільний день"
        summary = "День підходить для планування, спілкування і поступових дій."
    else:
        level = "🟣 сильний день"
        summary = "День має добрий потенціал для важливих кроків."

    focus = parts["numerology"]["theme"]

    recommendation = (
        f"{summary} Головна тема: {focus}. "
        f"Кармічний акцент: {parts['karmology']['lesson']}. "
        f"Цикл дня: {parts['cycle']['phase']} — {parts['cycle']['advice']}."
    )

    return {
        "level": level,
        "focus": focus,
        "recommendation": recommendation,
    }


def generate_safety_calendar(profile: Dict[str, Any]) -> Dict[str, Any]:
    birth_date = _parse_date(profile["birth_date"])
    start_date = _parse_date(profile.get("start_date") or date.today().isoformat())
    period_days = int(profile.get("period_days") or 7)
    period_days = max(1, min(period_days, 30))

    days: List[Dict[str, Any]] = []

    for i in range(period_days):
        target = start_date + timedelta(days=i)

        numerology = numerology_score(birth_date, target)
        karmology = karmology_score(birth_date, target)
        cycle = moon_like_cycle_score(target)

        total = round(
            numerology["score"] * 0.35
            + karmology["score"] * 0.35
            + cycle["score"] * 0.30
        )

        text = build_recommendation(total, {
            "numerology": numerology,
            "karmology": karmology,
            "cycle": cycle,
        })

        days.append({
            "date": target.isoformat(),
            "score": total,
            "level": text["level"],
            "focus": text["focus"],
            "recommendation": text["recommendation"],
            "debug": {
                "numerology": numerology,
                "karmology": karmology,
                "cycle": cycle,
            },
        })

    return {
        "ok": True,
        "profile": {
            "birth_date": birth_date.isoformat(),
            "birth_time": profile.get("birth_time"),
            "birth_place": profile.get("birth_place"),
            "current_location": profile.get("current_location"),
            "period_days": period_days,
            "start_date": start_date.isoformat(),
        },
        "days": days,
    }
