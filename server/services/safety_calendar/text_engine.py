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
        "Це рекомендаційний прогноз."
    )


def fallback_batch_texts(profile: Dict[str, Any], days: List[Dict[str, Any]]) -> Dict[str, str]:
    return {
        str(day.get("date")): fallback_day_text(profile, day)
        for day in days
        if day.get("date")
    }


def _build_prompt(profile: Dict[str, Any], days: List[Dict[str, Any]]) -> str:
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

    payload = {
        "profile": {
            "birth_date": profile.get("birth_date"),
            "birth_time": profile.get("birth_time"),
            "birth_place": profile.get("birth_place"),
            "current_location": profile.get("current_location"),
        },
        "days": compact_days,
    }

    return f"""
Ти пишеш персональні прогнози для Telegram-бота AstraNova українською мовою.

Вхідні дані:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Потрібно:
- створити окремий прогноз для кожної дати
- стиль преміальний, містичний, але практичний
- не давати гарантій подій
- не писати медичних/фінансових обіцянок
- HTML Telegram format
- тільки теги <b> і <i>
- максимум 1200 символів на день

Поверни СТРОГО JSON:

{{
  "items": [
    {{
      "date": "YYYY-MM-DD",
      "text": "HTML TEXT"
    }}
  ]
}}
"""


def _call_deepseek(prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY"),
        base_url=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
    )

    response = client.chat.completions.create(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        messages=[
            {
                "role": "system",
                "content": "Ти AI-астро-аналітик AstraNova.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.8,
        max_tokens=4000,
    )

    return response.choices[0].message.content.strip()


def _call_openai(prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    response = client.responses.create(
        model=os.getenv("ASTRANOVA_OPENAI_MODEL", "gpt-4.1-mini"),
        input=prompt,
    )

    return (response.output_text or "").strip()


def generate_ai_batch_texts(profile: Dict[str, Any], days: List[Dict[str, Any]]) -> Dict[str, str]:
    if not days:
        return {}

    prompt = _build_prompt(profile, days)

    raw = None

    # 1. DeepSeek
    try:
        if os.getenv("DEEPSEEK_API_KEY"):
            raw = _call_deepseek(prompt)
    except Exception as e:
        print("DEEPSEEK ERROR:", repr(e))

    # 2. OpenAI fallback
    if not raw:
        try:
            if os.getenv("OPENAI_API_KEY"):
                raw = _call_openai(prompt)
        except Exception as e:
            print("OPENAI ERROR:", repr(e))

    # 3. Fallback
    if not raw:
        return fallback_batch_texts(profile, days)

    try:
        raw = raw.strip()

        if raw.startswith("```"):
            raw = raw.strip("`")
            raw = raw.replace("json\n", "", 1)
            raw = raw.replace("JSON\n", "", 1)

        parsed = json.loads(raw)

        result = {}

        for item in parsed.get("items", []):
            d = str(item.get("date") or "").strip()
            t = str(item.get("text") or "").strip()

            if d and t:
                result[d] = t

        fallback = fallback_batch_texts(profile, days)

        for d, t in fallback.items():
            result.setdefault(d, t)

        return result

    except Exception as e:
        print("AI PARSE ERROR:", repr(e))
        return fallback_batch_texts(profile, days)
