"""Lightweight Meta Gateway for Render."""
import hmac
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse

from meta_webhook_receiver_v1 import (
    router as receiver_router,
    receive_meta_webhook,
)
from meta_queue_sync_api_v1 import router as sync_router
from meta_outbound_render_v1 import router as outbound_router

app = FastAPI(title="Meta Durable Gateway")

app.include_router(receiver_router)
app.include_router(sync_router)
app.include_router(outbound_router)


@app.get("/health")
def health():
    return {"ok": True, "service": "meta-gateway"}


@app.get("/webhook")
async def verify_meta(request: Request):
    params = request.query_params
    expected = os.getenv("META_VERIFY_TOKEN", "").strip()
    supplied = (params.get("hub.verify_token") or "").strip()

    if (
        not expected
        or params.get("hub.mode") != "subscribe"
        or not hmac.compare_digest(supplied, expected)
        or params.get("hub.challenge") is None
    ):
        raise HTTPException(403, "Verification failed")

    return PlainTextResponse(params["hub.challenge"])


@app.post("/webhook")
async def receive_existing_callback(request: Request):
    return await receive_meta_webhook(request)
