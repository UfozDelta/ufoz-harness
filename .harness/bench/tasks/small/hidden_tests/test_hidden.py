"""Hidden acceptance test, not shown to any arm. Run from the worktree root:
python -m pytest .harness/bench/tasks/small/hidden_tests/test_hidden.py -q
"""
from fastapi.testclient import TestClient

from app.main import app


def test_health_ok():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_health_is_get_only():
    r = TestClient(app).post("/health")
    assert r.status_code == 405
