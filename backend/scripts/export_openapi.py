import json
import sys
import os

# Prefer this repo's `app` package over anything else on PYTHONPATH
_backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _backend_dir in sys.path:
    sys.path.remove(_backend_dir)
sys.path.insert(0, _backend_dir)

from app.main import app
from fastapi.openapi.utils import get_openapi

def export():
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        openapi_version=app.openapi_version,
        description=app.description,
        routes=app.routes,
    )
    out = os.path.join(_backend_dir, "openapi.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

if __name__ == "__main__":
    export()