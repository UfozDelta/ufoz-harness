import json
from pathlib import Path

base = Path("bench/suite/fixtures")


def key(d):
    return [(t["id"], t.get("deps")) for t in d["tasks"]]


for size in ("small", "medium", "large"):
    new, old = base / size / "plan_project", base / size / "plan"
    for name in ("plan.md", "tasks.json"):
        text = (new / name).read_text(encoding="utf-8")
        assert "{work}" not in text and "bench/suite/work" not in text, (size, name)
    n = json.loads((new / "tasks.json").read_text(encoding="utf-8"))
    o = json.loads((old / "tasks.json").read_text(encoding="utf-8"))
    assert key(n) == key(o), size
    assert "{work}" in (old / "tasks.json").read_text(encoding="utf-8"), "plan/ must stay untouched"
print("T2 OK")
