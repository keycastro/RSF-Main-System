from __future__ import annotations

import os

import sys
import tempfile
from pathlib import Path

os.environ["RSF_DISABLE_BACKGROUND"] = "1"

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app

with tempfile.TemporaryDirectory() as tmp:
    app = create_app({
        "TESTING": True,
        "DATABASE": str(Path(tmp) / "smoke.db"),
        "SECRET_KEY": "smoke-check-only-not-production",
        "SERVER_NAME": "localhost",
    })
    client = app.test_client()
    response = client.get("/app/login")
    if response.status_code != 200 or b"Unified RSF System" not in response.data:
        raise SystemExit("Smoke check failed: login page did not render.")

print("Smoke check OK: login page rendered successfully without creating runtime data in the release folder.")
