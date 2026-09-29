import sys
from pathlib import Path

readme = Path("README.md").read_text(encoding="utf-8")
for s in ["--no-worktree", "--no-window", "HARNESS_WORKTREE=0", "HARNESS_WINDOW=0"]:
    if s not in readme:
        sys.exit(f"FAIL README.md lacks {s}")
for f in ["CLAUDE.md", ".harness/MAIN.md"]:
    t = Path(f).read_text(encoding="utf-8")
    if "git -C .worktrees/" not in t or "--no-worktree" not in t:
        sys.exit(f"FAIL {f} lacks worktree review/opt-out")
env = Path(".harness/.env.example").read_text(encoding="utf-8")
if "HARNESS_WORKTREE=0" not in env or "HARNESS_WINDOW=0" not in env:
    sys.exit("FAIL .env.example")
p = Path(".harness/plans/default-worktree/SUMMARY.md")
if not p.exists() or not 0 < len(p.read_text(encoding="utf-8")) <= 600:
    sys.exit("FAIL SUMMARY.md")
print("OK")
