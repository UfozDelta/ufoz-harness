"""usage: absent.py REGEX PATH... ; exit 1 if REGEX (case-insens) is found in a file or a PATH still exists
(prefix '!' on a path = must be absent)."""
import re, sys
from pathlib import Path
rx = re.compile(sys.argv[1], re.I)
bad = []
for a in sys.argv[2:]:
    if a.startswith("!"):
        if Path(a[1:]).exists():
            bad.append(f"exists: {a[1:]}")
        continue
    p = Path(a)
    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if rx.search(line):
            bad.append(f"{a}:{i}: {line.strip()[:80]}")
print("\n".join(bad))
sys.exit(1 if bad else 0)
