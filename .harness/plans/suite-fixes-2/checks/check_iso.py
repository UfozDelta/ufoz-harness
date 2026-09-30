"""Task isolation: every fixture task's acceptance must pass on seed + the reference solution
files of that task and its (transitive) deps only (what a serial run sees). Temp dirs live
under harness-suite/.check-tmp/ so node resolution finds the root node_modules."""
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


def check(size):
    fx = SUITE / "fixtures" / size
    tasks = json.loads((fx / "plan" / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    by_id = {t["id"]: t for t in tasks}
    bad = []
    for t in tasks:
        TMP.mkdir(parents=True, exist_ok=True)
        work = Path(tempfile.mkdtemp(prefix=f"iso-{size}-{t['id']}-", dir=TMP))
        try:
            shutil.copytree(fx / "seed", work, dirs_exist_ok=True)
            for tid in {t["id"], *ancestors(t["id"], by_id)}:
                for f in by_id[tid]["files"]:
                    rel = f.replace("{work}/", "")
                    src = fx / "solution" / rel
                    if src.is_file():
                        (work / rel).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(src, work / rel)
            cmd = t["acceptance"].replace("{work}", str(work))
            r = subprocess.run(cmd, shell=True, cwd=ROOT, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL)
            if r.returncode != 0:
                bad.append(f"{size} {t['id']}: {(r.stdout + r.stderr).strip()[-300:]}")
        finally:
            shutil.rmtree(work, ignore_errors=True)
    return bad


if __name__ == "__main__":
    failures = [line for size in ("small", "medium", "large") for line in check(size)]
    print("\n".join(failures) or "ISOLATION OK")
    sys.exit(1 if failures else 0)
