"""Acceptance check for T2. Run from project root: python .harness/plans/bench-plan/checks/check_t2.py"""
from fastapi.testclient import TestClient

from app.main import app, reset_store

client = TestClient(app)
reset_store()

r = client.get("/health")
assert r.status_code == 200, r.status_code
assert r.json() == {"status": "ok"}, r.json()

r = client.get("/items")
assert r.status_code == 200, r.status_code
assert r.json() == [], r.json()

r = client.get("/items/1")
assert r.status_code == 404, r.status_code
assert "detail" in r.json(), r.json()

print("GET OK")
