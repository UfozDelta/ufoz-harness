from fastapi.testclient import TestClient
from app.main import app

r = TestClient(app).get("/health")
assert r.status_code == 200 and r.json() == {"status": "ok"}, (r.status_code, r.text)
print("HEALTH OK")
