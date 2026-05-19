from __future__ import annotations

import json
import os
from typing import Any, Dict, List


def fallback_day_text(profile: Dict[str, Any], day: Dict[str, Any]) -> str:
    return (
        f"✨ <b>AstraNova · {day.get('date')}</b>\n\n"
        f"{day.get('level')}\n"
        f"Індекс: <b>{day.get('score')}/100</b>\n\n"
        f"🌙 <b>Фокус дня:</b>\n{day.get('focus')}\n\n"
        f"🧭 <b>Рекомендація:</b>\n{day.get('recommendation')}\n\n"
        "Це рекомендаційний прогноз, а не гарантія подій."
    )


def fallback_batch_texts(profile: Dict[str, Any], days: List[Dict[str, Any]]) -> Dict[str, str]:
    return {
        str(day.get("date")): fallback_day_text(profile, day)
        for day in days
        if day.get("date")
    }


def generate_ai_batch_texts(profile: Dict[str, Any], days: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Економний режим:
    один OpenAI-запит генерує тексти одразу для всіх днів періоду.
    Повертає dict: {YYYY-MM-DD: html_text}
    """
    if not days:
        return {}

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return fallback_batch_texts(profile, days)

    compact_days = []
    for day in days:
        compact_days.append({
            "date": day.get("date"),
            "score": day.get("score"),
            "level": day.get("level"),
            "focus": day.get("focus"),
            "recommendation": day.get("recommendation"),
            "debug": day.get("debug"),
        })

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        payload = {
            "profile": {
                "birth_date": profile.get("birth_date"),
                "birth_time": profile.get("birth_time"),
                "birth_place": profile.get("birth_place"),
                "current_location": profile.get("current_location"),
            },
            "days": compact_days,
        }

        prompt = f"""
Ти пишеш персональні щоденні прогнози для Telegram-бота AstraNova українською мовою.

Вхідні дані:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Завдання:
- Згенеруй окремий текст для кожної дати.
- Не обіцяй точних подій.
- Не давай медичних, юридичних або фінансових гарантій.
- Пояснюй індекс через персональний цикл, тему дня, емоції, рішення, комунікацію, фінанси.
- Стиль: преміальний, містичний, але тверезий і практичний.
- Формат тексту: Telegram HTML.
- Дозволені HTML-теги тільки: <b>, <i>.
- Кожен текст до 1200 символів.
- Не використовуй Markdown.
- Не додавай зайвий текст поза JSON.

Поверни СТРОГО валідний JSON такого формату:
{{
  "items": [
    {{
      "date": "YYYY-MM-DD",
      "text": "HTML text for Telegram"
    }}
  ]
}}
"""

        response = client.responses.create(
            model=os.getenv("ASTRANOVA_OPENAI_MODEL", "gpt-4.1-mini"),
            input=prompt,
        )

        raw = (response.output_text or "").strip()

        # захист від ```json ... ```
        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json\n", "", 1).replace("JSON\n", "", 1).strip()

        parsed = json.loads(raw)
        items = parsed.get("items") or []

        result: Dict[str, str] = {}

        for item in items:
            d = str(item.get("date") or "").strip()
            t = str(item.get("text") or "").strip()
            if d and t:
                result[d] = t

        fallback = fallback_batch_texts(profile, days)

        # якщо AI не повернув якийсь день — добиваємо fallback
        for d, t in fallback.items():
            result.setdefault(d, t)

        return result

    except Exception as e:
        print("ASTRANOVA AI batch text error:", repr(e))
        return fallback_batch_texts(profile, days)
