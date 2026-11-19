"""Render startup: lightweight Meta Gateway."""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    print("META_GATEWAY_STARTING", flush=True)
    uvicorn.run(
        "meta_gateway_app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
    )
