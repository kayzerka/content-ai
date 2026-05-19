from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(tags=["astranova-bot"])


@router.post("/webhook/astranova")
async def astranova_webhook(request: Request):
    data = await request.json()

    print("ASTRANOVA UPDATE:", data)

    return {"ok": True}
