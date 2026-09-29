import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

PKG = Path("packages/ufoz-harness")
KIT = PKG / "kit"
SH = os.name == "nt"


def run(cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=SH, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        sys.exit(f"FAIL {cmd}: {r.stdout[-800:]}{r.stderr[-800:]}")
    return r.stdout


run([sys.executable, "export_kit.py"], cwd=PKG)
need = ["CLAUDE.md", "AGENTS.md", "opencode.json", ".claude/agents/planner.md",
        ".claude/agents/reviewer.md", ".claude/settings.json", ".claude/skills/adhd/SKILL.md",
        ".claude/skills/animate/SKILL.md", ".claude/skills/caveman-explore/SKILL.md",
        ".pi/deny.json", ".pi/executor.md", ".pi/extensions/deny-list.ts", ".pi/extensions/deny-match.ts",
        ".opencode/agent/executor.md", ".opencode/package.json",
        ".agents/skills/frontend-design/SKILL.md", ".agents/skills/animate/SKILL.md", "skills-lock.json", ".harness/run_plan.py", ".harness/selftest.py",
        ".harness/build_map.py", ".harness/envfile.py", ".harness/.env.example", ".harness/MAIN.md",
        ".harness/CHECK_PATTERNS.md", ".harness/README.md", ".harness/plans/.gitkeep"]
need += [str(p.relative_to(".")).replace("\\", "/") for p in Path(".harness/runner").rglob("*.py")]
for rel in need:
    if not (KIT / rel).is_file():
        sys.exit(f"FAIL kit missing {rel}")
files = [p.relative_to(KIT).as_posix() for p in KIT.rglob("*") if p.is_file()]
bad = [f for f in files if f == ".harness/.env" or "__pycache__" in f or f.startswith(".harness/bench")
       or f.startswith(".harness/context") or f.endswith(".test.mjs") or f.endswith("validator.md")
       or f.startswith("tests/") or "node_modules" in f]
if bad:
    sys.exit(f"FAIL kit has forbidden files: {bad[:5]}")
pj = json.loads((PKG / "package.json").read_text(encoding="utf-8"))
if pj.get("version") != "0.3.0" or "export_kit.py" not in pj.get("scripts", {}).get("prepack", ""):
    sys.exit("FAIL package.json version/prepack")
if ".harness/.env'" not in (PKG / "index.js").read_text(encoding="utf-8"):
    sys.exit("FAIL index.js IGNORE_LINES lacks .harness/.env")
run(["node", "--test"], cwd=PKG)
tmp = tempfile.mkdtemp(prefix="ufoz-e2e-")
try:
    run(["node", str(PKG / "index.js"), "--yes", "--dir", tmp])
    if ".harness/.env" not in Path(tmp, ".gitignore").read_text(encoding="utf-8").splitlines():
        sys.exit("FAIL installed .gitignore lacks .harness/.env")
    out = run([sys.executable, ".harness/run_plan.py", "--help"], cwd=tmp)
    if "usage" not in out.lower():
        sys.exit("FAIL run_plan --help in installed dir")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
packed = run(["npm", "pack", "--dry-run", "--json", "--ignore-scripts"], cwd=PKG)
paths = {f["path"] for f in json.loads(packed)[0]["files"]}
for rel in ["index.js", "kit/.harness/runner/cli.py", "kit/.claude/settings.json", "kit/.pi/deny.json"]:
    if rel not in paths:
        sys.exit(f"FAIL npm pack missing {rel}")
print("OK")
