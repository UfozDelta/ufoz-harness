"""Acceptance check for T2. Run from project root: python .harness/plans/bench-plan/checks/check_t2.py

Mounts the router on a throwaway FastAPI app, so it passes before app/main.py is updated.
"""
import os
import sys

sys.path.insert(0, os.getcwd())

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import store
from app.routers.items import router

probe = FastAPI()
probe.include_router(router)
client = TestClient(probe)

store.reset_store()

assert client.get("/items").json() == [], client.get("/items").json()
assert client.get("/items/1").status_code == 404

r = client.post("/items", json={"name": "widget", "price": 9.5})
assert r.status_code == 201, (r.status_code, r.text)
assert r.json() == {"id": 1, "name": "widget", "price": 9.5}, r.json()

r = client.post("/items", json={"name": "gadget", "price": 0})
assert r.json()["id"] == 2, r.json()

assert client.get("/items/2").json()["name"] == "gadget"
assert len(client.get("/items").json()) == 2
assert len(store.items) == 2, "router must write into app.store.items"

for bad in ({"name": "", "price": 1}, {"name": "a", "price": -1}, {"price": 1}, {}):
    assert client.post("/items", json=bad).status_code == 422, bad

store.reset_store()
assert client.get("/items").json() == []

print("ROUTER OK")
