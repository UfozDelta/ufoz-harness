"""prepare_cell must template {work} in plan.md as well as tasks.json (both copies)."""
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "harness-suite"))
import cells  # noqa: E402

slug = "suite-small-serial-checkt2-r0"
main_plan = ROOT / ".harness" / "plans" / slug
bad = []
with tempfile.TemporaryDirectory() as d:
    fake_wt = Path(d) / "wt"
    fake_wt.mkdir()
    cells.worktree.ensure = lambda *a, **k: fake_wt  # no real worktree for this check
    try:
        cells.prepare_cell({"slug": slug, "size": "small", "mode": "serial", "executor": "pi"}, ROOT)
        for plan in (fake_wt / ".harness" / "plans" / slug, main_plan):
            text = (plan / "plan.md").read_text(encoding="utf-8")
            if "{work}" in text or f"harness-suite/work/{slug}" not in text:
                bad.append(f"{plan}: plan.md not templated")
    finally:
        shutil.rmtree(main_plan, ignore_errors=True)
print("\n".join(bad) or "TEMPLATE OK")
sys.exit(1 if bad else 0)
