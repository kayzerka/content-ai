import json, time
from pathlib import Path

p = Path("backups/funnels-latest.json")
d = json.loads(p.read_text(encoding="utf-8"))

tables = d.setdefault("tables", {})

plans = tables.get("ig_reaction_funnel_plans", [])
configs = tables.setdefault("funnel_configs", [])

existing = {x.get("funnel_key") for x in configs}
now = int(time.time())
added = 0

for r in plans:
    key = r.get("plan_key")
    if not key or key in existing:
        continue

    configs.append({
        "funnel_key": key,
        "name": r.get("plan_name") or key,
        "description": r.get("plan_goal") or r.get("notes") or "",
        "trigger_type": "keyword",
        "trigger_value": r.get("trigger_keywords") or "",
        "output_type": "telegram_bot",
        "output_target": "@content_ai_planner_bot",
        "enabled": int(r.get("active", 1)),
        "created_at": r.get("created_at") or now,
        "updated_at": r.get("updated_at") or now
    })

    existing.add(key)
    added += 1

p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

print("added:", added)
print("total funnel_configs:", len(tables.get("funnel_configs", [])))
