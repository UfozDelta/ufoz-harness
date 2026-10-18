import sys, tempfile
from pathlib import Path
sys.path.insert(0, "bench/verify")
import verify
class C:
    pass
with tempfile.TemporaryDirectory() as t:
    root = Path(t)
    for n in ("verify-a-r1", "verify-me-r1", "suite-keep", "_kit", "_specs"):
        (root / n).mkdir()
    c = C(); c.TEMP_ROOT = root
    verify._wipe_stale(c, "verify-me-r1")
    left = sorted(p.name for p in root.iterdir())
    assert left == ["_kit", "_specs", "suite-keep", "verify-me-r1"], left
cell = {"slug": "verify-x-r1", "size": "small"}
with tempfile.TemporaryDirectory() as t:
    brief = verify._plan_brief(cell, t)
    assert "current directory" in brief
