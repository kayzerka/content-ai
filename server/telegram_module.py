
# TELEGRAM_SEED_DEFAULTS_FREE_RENDER_V1
@router.post("/chats/seed_defaults")
def telegram_seed_defaults():
    import json
    from pathlib import Path

    seed_path = Path(__file__).resolve().parent / "telegram_seed.json"
    if not seed_path.exists():
        return {"ok": False, "error": "telegram_seed_json_not_found", "path": str(seed_path)}

    items = json.loads(seed_path.read_text(encoding="utf-8"))
    results = []

    for payload in items:
        try:
            res = telegram_chat_manual_upsert_v2(payload)
            results.append(res)
        except Exception as e:
            results.append({
                "ok": False,
                "chat_id": payload.get("chat_id"),
                "error": repr(e)
            })

    return {
        "ok": all(bool(r.get("ok")) for r in results),
        "count": len(results),
        "results": results
    }

# TELEGRAM_SEED_DEFAULTS_FREE_RENDER_V1
@router.post("/chats/seed_defaults")
def telegram_seed_defaults():
    import json
    from pathlib import Path

    seed_path = Path(__file__).resolve().parent / "telegram_seed.json"
    if not seed_path.exists():
        return {"ok": False, "error": "telegram_seed_json_not_found", "path": str(seed_path)}

    items = json.loads(seed_path.read_text(encoding="utf-8"))
    results = []

    for payload in items:
        try:
            res = telegram_chat_manual_upsert_v2(payload)
            results.append(res)
        except Exception as e:
            results.append({"ok": False, "chat_id": payload.get("chat_id"), "error": repr(e)})

    return {"ok": all(bool(r.get("ok")) for r in results), "count": len(results), "results": results}
