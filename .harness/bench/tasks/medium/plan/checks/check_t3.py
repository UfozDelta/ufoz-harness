"""Acceptance check for T3. Run from project root: python .harness/plans/bench-plan/checks/check_t3.py"""
from fastapi.testclient import TestClient

from app.main import app, reset_store

client = TestClient(app)
reset_store()

r = client.post("/items", json={"name": "widget", "price": 9.5})
assert r.status_code == 201, (r.status_code, r.text)
created = r.json()
assert created == {"id": 1, "name": "widget", "price": 9.5}, created

r = client.post("/items", json={"name": "gadget", "price": 0})
assert r.status_code == 201, (r.status_code, r.text)
assert r.json()["id"] == 2, r.json()

assert client.get("/items").json() == [
    {"id": 1, "name": "widget", "price": 9.5},
    {"id": 2, "name": "gadget", "price": 0},
], client.get("/items").json()

assert client.get("/items/2").json()["name"] == "gadget"

for bad in ({"name": "", "price": 1}, {"name": "a", "price": -1}, {"price": 1}, {}):
    assert client.post("/items", json=bad).status_code == 422, bad

reset_store()
assert client.get("/items").json() == []

print("POST OK")
