import sys
from pathlib import Path

DOCS = ["README.md", "CLAUDE.md", ".harness/MAIN.md", "docs/FLOWS.md", "docs/ARCHITECTURE.md",
        "packages/ufoz-harness/README.md", "packages/ufoz-harness/kit_readme.md"]

for name in DOCS:
    path = Path(name)
    assert path.is_file(), f"{name} is missing"
    text = path.read_text(encoding="utf-8")
    assert "land.patch" not in text, f"{name} still documents land.patch"
    assert "--land" in text, f"{name} stopped documenting --land (it still exists in T4)"
    if name in ("README.md", "CLAUDE.md", ".harness/MAIN.md"):
        assert "clean" in text.lower(), f"{name} does not say the tree must be clean before a run"

env_example = Path(".harness/.env.example").read_text(encoding="utf-8")
assert "HARNESS_COMMIT_STYLE" in env_example, ".env.example does not document HARNESS_COMMIT_STYLE"

summary = Path(".harness/plans/worktree-commits/SUMMARY.md")
assert summary.is_file(), "SUMMARY.md was not written"
body = summary.read_text(encoding="utf-8").strip()
assert 0 < len(body) <= 600, f"SUMMARY.md is {len(body)} chars (max 600)"
print("OK")