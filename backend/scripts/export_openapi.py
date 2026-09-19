import json
import sys
import os

# Add backend dir to sys.path so we can import app
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

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
    with open("openapi.json", "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)

if __name__ == "__main__":
    export()