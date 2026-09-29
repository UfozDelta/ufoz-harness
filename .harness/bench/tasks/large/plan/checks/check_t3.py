"""Acceptance check for T3. Run from project root: python .harness/plans/bench-plan/checks/check_t3.py"""
import os
import subprocess
import sys

sys.path.insert(0, os.getcwd())

from fastapi.testclient import TestClient

import app.main as main
from app import store
from app.main import app as fastapi_app, reset_store

assert reset_store is store.reset_store, "app.main must re-export app.store.reset_store"
assert not hasattr(main, "_items"), "app/main.py must no longer define _items"
assert not hasattr(main, "_next_id"), "app/main.py must no longer define _next_id"

client = TestClient(fastapi_app)
reset_store()

assert client.get("/health").json() == {"status": "ok"}
assert client.get("/items").json() == []
assert client.get("/items/1").status_code == 404

r = client.post("/items", json={"name": "widget", "price": 9.5})
assert r.status_code == 201, (r.status_code, r.text)
assert r.json() == {"id": 1, "name": "widget", "price": 9.5}, r.json()
assert client.get("/items/1").json() == {"id": 1, "name": "widget", "price": 9.5}
assert client.post("/items", json={"name": "", "price": 1}).status_code == 422
assert len(store.items) == 1, store.items

reset_store()
assert client.get("/items").json() == []

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_items.py", "-q"],
    cwd=os.getcwd(),
)
assert result.returncode == 0, "existing tests/test_items.py must still pass"

print("MAIN OK")
