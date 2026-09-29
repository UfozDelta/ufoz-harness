"""Acceptance check for docs-move T1. Hash-locked: the executor cannot edit this."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
MOVED = ["FLOWS.md", "ARCHITECTURE.md", "mermaid.md"]

fail = []

# 1. originals gone from the root, present in docs/
for name in MOVED:
    if (ROOT / name).exists():
        fail.append(f"still at repo root: {name}")
    if not (ROOT / "docs" / name).exists():
        fail.append(f"missing from docs/: {name}")

readme = (ROOT / "README.md").read_text(encoding="utf-8")

# 2. README must not carry bare or root-relative references
if "[mermaid.md](mermaid.md)" in readme:
    fail.append("README.md still has root-relative mermaid.md link")
if "`ARCHITECTURE.md` explains" in readme:
    fail.append("README.md still says `ARCHITECTURE.md` explains")
if "see ARCHITECTURE.md for details" in readme:
    fail.append("README.md still says 'see ARCHITECTURE.md for details'")

# every remaining ARCHITECTURE.md mention in README must be docs/-prefixed
for i, line in enumerate(readme.splitlines(), 1):
    if "ARCHITECTURE.md" in line and "docs/ARCHITECTURE.md" not in line:
        fail.append(f"README.md:{i} mentions ARCHITECTURE.md without docs/ prefix")

# 3. the one link that needed fixing
arch = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
if "[README.md](README.md)" in arch:
    fail.append("docs/ARCHITECTURE.md still links to README.md without ../")
if "[README.md](../README.md)" not in arch:
    fail.append("docs/ARCHITECTURE.md is missing the ../README.md link")

if fail:
    print("FAIL")
    for f in fail:
        print("  -", f)
    sys.exit(1)

print("PASS: 3 docs in docs/, originals gone, README refs prefixed, ../README.md link fixed")
