import os
import traceback

print("=== RENDER START DIAGNOSTIC ===", flush=True)

try:
    import app
    print("=== APP IMPORT OK ===", flush=True)
except Exception:
    print("=== APP IMPORT FAILED ===", flush=True)
    traceback.print_exc()
    raise

import uvicorn

port = int(os.environ.get("PORT", "10000"))
uvicorn.run("app:app", host="0.0.0.0", port=port)
