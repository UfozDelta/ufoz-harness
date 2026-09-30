"""Red on seed: every fixture task's acceptance must FAIL on seed + the reference solution of
its (transitive) deps, i.e. before the task's own work. Seed stubs made some checks pass
early (large T5: CHECK-INVALID). Also: every fixture plan.md names its work dir."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SUITE = ROOT / "harness-suite"
TMP = SUITE / ".check-tmp"


def ancestors(tid, by_id):
    seen, pending = set(), list(by_id[tid].get("deps", []))
    while pending:
        d = pending.pop()
        if d not in seen:
            seen.add(d)
            pending.extend(by_id[d].get("deps", []))
    return seen


bad = []
for size in ("small", "medium", "large"):
    fx = SUITE / "fixtures" / size
    plan_md = (fx / "plan" / "plan.md").read_text(encoding="utf-8")
    if "Work dir: `{work}`" not in plan_md:
        bad.append(f"{size}: plan.md lacks the line 'Work dir: `{{work}}` ...'")
    tasks = json.loads((fx / "plan" / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    by_id = {t["id"]: t for t in tasks}
    for t in tasks:
        TMP.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=f"red-{size}-{t['id']}-", dir=TMP))
        try:
            shutil.copytree(fx / "seed", work, dirs_exist_ok=True)
            for tid in ancestors(t["id"], by_id):
                for f in by_id[tid]["files"]:
                    rel = f.replace("{work}/", "")
                    src = fx / "solution" / rel
                    if src.is_file():
                        (work / rel).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(src, work / rel)
            r = subprocess.run(t["acceptance"].replace("{work}", str(work)), shell=True, cwd=ROOT,
                               capture_output=True, text=True, encoding="utf-8", errors="replace",
                               stdin=subprocess.DEVNULL)
            if r.returncode == 0:
                bad.append(f"{size} {t['id']}: acceptance passes before the task's own work")
        finally:
            shutil.rmtree(work, ignore_errors=True)
print("\n".join(bad) or "RED OK")
sys.exit(1 if bad else 0)
