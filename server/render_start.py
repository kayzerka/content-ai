import os
import sys
import traceback

print("=== RENDER START DIAGNOSTIC V2 ===", flush=True)
print("cwd:", os.getcwd(), flush=True)
print("files:", os.listdir("."), flush=True)

try:
    print("=== IMPORTING APP ===", flush=True)
    import app
    print("=== APP IMPORT OK ===", flush=True)
except BaseException as e:
    print("=== APP IMPORT FAILED ===", flush=True)
    print("type:", type(e).__name__, flush=True)
    print("repr:", repr(e), flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
    sys.stderr.flush()
    raise

try:
    import uvicorn
    port = int(os.environ.get("PORT", "10000"))
    print("=== STARTING UVICORN ON PORT", port, "===", flush=True)
    uvicorn.run("app:app", host="0.0.0.0", port=port, log_level="debug")
except BaseException as e:
    print("=== UVICORN FAILED ===", flush=True)
    print("type:", type(e).__name__, flush=True)
    print("repr:", repr(e), flush=True)
    traceback.print_exc(file=sys.stdout)
    sys.stdout.flush()
    sys.stderr.flush()
    raise
