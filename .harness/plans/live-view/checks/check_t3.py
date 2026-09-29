import sys
from pathlib import Path

readme = Path("README.md").read_text(encoding="utf-8")
for s in ["--watch", "--window", "HARNESS_WINDOW"]:
    if s not in readme:
        sys.exit(f"FAIL README.md lacks {s}")
for f in ["CLAUDE.md", ".harness/MAIN.md"]:
    if "--window" not in Path(f).read_text(encoding="utf-8"):
        sys.exit(f"FAIL {f} lacks --window")
p = Path(".harness/plans/live-view/SUMMARY.md")
if not p.exists() or not 0 < len(p.read_text(encoding="utf-8")) <= 600:
    sys.exit("FAIL SUMMARY.md")
print("OK")
