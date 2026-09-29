import io
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".harness")
from runner import watch as w  # noqa: E402

r = w.render_line
assert r("") is None and r("   \r\n") is None
got = r('[toolCall bash] {"command": "npm test\\nmore"}')
assert got == "  bash   npm test", got
assert r('[toolCall read] {"path": "a.py"}') == "  read   a.py"
assert r('[toolCall edit] {"edits": [{"oldText": "x", "newT') == '  edit   {"edits": [{"oldText": "x", "newT'
assert len(r("[toolCall bash] " + json.dumps({"command": "x" * 500}))) == 110
assert r("[tool error] boom") == "  ✖ tool error: boom"
assert r("DONE: a.py") == "  ✔ DONE: a.py"
assert r("BLOCKED: no") == "  ✖ BLOCKED: no"
assert r("hello\r\n") == "  │ hello"
colored = r("[tool error] boom", color=True)
assert "\x1b[" in colored and "boom" in colored
assert w.log_title("T4.pi.log") == "T4"
assert w.log_title("T4.retry1.pi.log") == "T4 retry 1"
assert w.log_title("T4.repair2.claude.log") == "T4 repair 2"
assert w.log_title("planner.log") == "planner"
rep = "RESULT: pass\nexec seconds: 41.3\nacceptance seconds: 1.2\n"
assert w.report_line("T4", rep) == "✔ T4 pass · exec 41s · accept 1.2s", w.report_line("T4", rep)
assert w.report_line("T4", "RESULT: fail\n") == "✖ T4 fail"
assert w.report_line("T4", "RESULT: running\nstarted: x\n") is None
assert w.report_line("T4", "") is None

orig = w.shutil.which
w.shutil.which = lambda c: "C:/wt.exe" if c == "wt" else None
c = w.window_command("demo")
assert c[:5] == ["wt", "-w", "new", "--title", "harness demo"] and c[5] == "-d", c
assert c[-6:] == ["cmd", "/k", sys.executable, ".harness/run_plan.py", "demo", "--watch"], c
w.shutil.which = lambda c: None
c = w.window_command("demo")
assert c[:4] == ["cmd", "/c", "start", "harness demo"] and c[-1] == "--watch", c
w.shutil.which = orig
calls = []
w.subprocess.Popen = lambda cmd, *a, **k: calls.append(cmd)
assert w.open_window("demo") is True and calls

d = Path(tempfile.mkdtemp()) / "demo"
(d / "logs").mkdir(parents=True)
(d / "items").mkdir()
(d / "tasks.json").write_text(json.dumps({"slug": "demo", "tasks": [{"id": "T1"}, {"id": "T2"}]}), encoding="utf-8")
(d / "logs/T1.pi.log").write_text('[toolCall read] {"path": "a.py"}\nDONE: a.py\n', encoding="utf-8")
(d / "logs/T2.retry1.pi.log").write_text("[tool error] bad\n", encoding="utf-8")
(d / "items/T1.report.md").write_text(rep, encoding="utf-8")
(d / "items/T2.report.md").write_text("RESULT: fail\n", encoding="utf-8")
out = io.StringIO()
assert w.watch(d, poll=0.05, wait_start=5, out=out) == 0
s = out.getvalue()
for want in ["harness · demo", "▶ T1", "  read   a.py", "✔ DONE: a.py", "▶ T2 retry 1",
             "✖ tool error: bad", "✔ T1 pass", "✖ T2 fail", "done: 1/2 pass"]:
    assert want in s, (want, s)
assert "\x1b[" not in s
assert w.watch(d.parent / "nope", out=io.StringIO()) == 1
print("OK")
