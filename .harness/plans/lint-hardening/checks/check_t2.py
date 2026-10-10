import io, json, sys, tempfile, contextlib
from pathlib import Path
sys.path.insert(0, ".harness")
from runner import lint as L

def run(acc, plat):
    d = Path(tempfile.mkdtemp())
    (d / "plan.md").write_text("## T1\n", encoding="utf-8")
    t = [{"id": "T1", "deps": [], "files": ["a.py"], "acceptance": acc, "red_first": False, "red_first_reason": "x"}]
    old, L.sys.platform = L.sys.platform, plat
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            L.lint(d, t, set())
    finally:
        L.sys.platform = old
    return buf.getvalue()

for acc in ("! grep x f", "test -f a", "rm x"):
    assert "POSIX" in run(acc, "win32"), acc
    assert "POSIX" not in run(acc, "linux"), acc
assert "POSIX" not in run('python -c "print(1)"', "win32")
