"""Exit 1 if any given file still mentions cline (case-insensitive). Missing file = ok (deleted)."""
import sys
from pathlib import Path

bad = []
for f in sys.argv[1:]:
    p = Path(f)
    if p.exists() and "cline" in p.read_text(encoding="utf-8", errors="ignore").lower():
        bad.append(f)
if bad:
    sys.exit("still mentions cline: " + ", ".join(bad))
