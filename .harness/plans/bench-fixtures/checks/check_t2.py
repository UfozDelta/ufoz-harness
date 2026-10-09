import json
from pathlib import Path

base = Path("bench/suite/fixtures")
for d in ("medium/seed", "large/seed/web"):
    p = json.loads((base / d / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((base / d / "package-lock.json").read_text(encoding="utf-8"))
    root = lock["packages"][""]
    assert p["devDependencies"], d
    assert p["devDependencies"] == root["devDependencies"], d
    assert lock["name"] == p["name"] == root["name"], d
    assert "test" in p["scripts"], d
print("T2 OK")
