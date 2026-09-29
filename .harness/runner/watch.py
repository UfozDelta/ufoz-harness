"""Live view of a running plan: follow the executor logs in this terminal, pretty."""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

DETAIL_KEYS = ("path", "command", "file_path", "filePath", "pattern", "url")
EXECUTORS = ("pi", "claude", "opencode", "cline", "cline-acp", "llama")
WIDTH = 110
RESET, CYAN, RED, GREEN, DIM = "\x1b[0m", "\x1b[36m", "\x1b[31m", "\x1b[32m", "\x1b[2m"

if os.name == "nt":
    os.system("")  # turn on the console's VT processing so the colors below show up


def _paint(text, code):
    return f"{code}{text}{RESET}"


def render_line(line, color=False):
    """One log line as one display line, or None if there is nothing to show."""
    line = line.rstrip("\r\n")
    if not line.strip():
        return None
    if line.startswith("[toolCall "):
        name, _, args = line[len("[toolCall "):].partition("]")
        name = name.strip()
        detail = _detail(args.strip())
        if color:
            return f"  {_paint(f'{name:<6}', CYAN)}{detail}"
        return f"  {name:<6} {detail}"[:WIDTH]
    if line.startswith("[tool error] "):
        out = "  ✖ tool error: " + line[len("[tool error] "):]
        return _paint(out, RED) if color else out
    if line.startswith("DONE:"):
        out = "  ✔ " + line
        return _paint(out, GREEN) if color else out
    if line.startswith("BLOCKED:"):
        out = "  ✖ " + line
        return _paint(out, RED) if color else out
    out = "  │ " + line
    return _paint(out, DIM) if color else out


def _detail(args):
    """The one interesting argument of a tool call, or the raw (maybe truncated) text."""
    try:
        obj = json.loads(args.split("\n", 1)[0])
    except ValueError:
        return args
    if isinstance(obj, dict):
        for key in DETAIL_KEYS:
            if key in obj:
                return str(obj[key]).split("\n", 1)[0]
    return args


def log_title(name):
    """`T4.repair2.claude.log` -> `T4 repair 2`; `planner.log` -> `planner`."""
    stem = name[:-4] if name.endswith(".log") else name
    parts = stem.split(".")
    if len(parts) > 1 and parts[-1] in EXECUTORS:
        parts = parts[:-1]
    out = parts[0]
    for part in parts[1:]:
        for kind in ("retry", "repair"):
            if part.startswith(kind) and part[len(kind):].isdigit():
                part = f"{kind} {part[len(kind):]}"
                break
        out += f" {part}"
    return out


def _field(text, key):
    for line in text.splitlines():
        if line.startswith(key):
            return line[len(key):].strip()
    return None


def report_line(tid, text, color=False):
    """The one line per finished task: pass/fail plus the recorded times."""
    result = _field(text, "RESULT: ")
    if not result or result == "running":
        return None
    if result == "pass":
        out = f"✔ {tid} pass"
    else:
        out = f"✖ {tid} {result}"
    secs = _field(text, "exec seconds: ")
    if secs:
        try:
            out += f" · exec {int(float(secs))}s"
        except ValueError:
            pass
    accept = _field(text, "acceptance seconds: ")
    if accept:
        out += f" · accept {accept}s"
    return _paint(out, GREEN if result == "pass" else RED) if color else out


def _read_from(path, offset):
    """Bytes from offset up to the last complete line, and the new offset."""
    try:
        with open(path, "rb") as fh:
            fh.seek(offset)
            data = fh.read()
    except OSError:
        return offset, []
    end = data.rfind(b"\n")
    if end < 0:
        return offset, []
    chunk = data[:end + 1]
    return offset + len(chunk), chunk.decode("utf-8", "replace").splitlines()


def _logs(logs_dir):
    if not logs_dir.is_dir():
        return []
    files = [p for p in logs_dir.glob("*.log") if p.is_file()]
    return sorted(files, key=lambda p: (p.stat().st_mtime, p.name))


def _task_ids(plan_dir):
    try:
        data = json.loads((plan_dir / "tasks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [t.get("id") for t in data.get("tasks", []) if t.get("id")]


def _result(text):
    return _field(text, "RESULT: ") or ""


def watch(plan_dir, poll=0.5, wait_start=30.0, out=None):
    """Replay the logs of a plan, then follow them until the run is over."""
    out = sys.stdout if out is None else out
    if hasattr(out, "reconfigure"):  # a legacy console codepage cannot encode the marks below
        try:
            out.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
    color = bool(getattr(out, "isatty", lambda: False)())
    plan_dir = Path(plan_dir)
    if not plan_dir.is_dir():
        print(f"no plan directory at {plan_dir}", file=out)
        return 1
    logs_dir, items_dir, lock = plan_dir / "logs", plan_dir / "items", plan_dir / "run.lock"
    tids = _task_ids(plan_dir)
    out.write(f"━━ harness · {plan_dir.name} ━━\n")
    out.flush()

    offsets, current, results = {}, None, {}

    def sweep():
        nonlocal current
        for path in _logs(logs_dir):
            offset, lines = _read_from(path, offsets.get(path, 0))
            offsets[path] = offset
            if not lines:
                continue
            title = log_title(path.name)
            if title != current:
                out.write(f"▶ {title} {time.strftime('%H:%M:%S')}\n")
                current = title
            for line in lines:
                shown = render_line(line, color=color)
                if shown:
                    out.write(shown + "\n")
        for tid in tids:
            try:
                text = (items_dir / f"{tid}.report.md").read_text(encoding="utf-8")
            except OSError:
                continue
            result = _result(text)
            if result and results.get(tid) != result:
                results[tid] = result
                shown = report_line(tid, text, color=color)
                if shown:
                    out.write(shown + "\n")
        out.flush()

    start, lock_seen = time.time(), lock.exists()
    try:
        while True:
            sweep()
            if lock.exists():
                lock_seen = True
            if not lock.exists():
                settled = bool(tids) and all(
                    results.get(tid) and results[tid] != "running" for tid in tids)
                if lock_seen or settled or time.time() - start > wait_start:
                    sweep()  # final drain
                    break
            time.sleep(poll)
    except KeyboardInterrupt:
        out.write("\nwatch stopped\n")
        out.flush()
        return 130
    passed = sum(1 for tid in tids if results.get(tid) == "pass")
    out.write(f"━━ done: {passed}/{len(tids)} pass ━━\n")
    out.flush()
    return 0


def window_command(slug):
    """The command that opens a new terminal window watching this plan."""
    tail = ["cmd", "/k", sys.executable, ".harness/run_plan.py", slug, "--watch"]
    if shutil.which("wt"):
        # one shared window, one tab per plan
        return ["wt", "-w", "harness", "new-tab", "--title", f"harness {slug}",
                "-d", os.getcwd(), *tail]
    return ["cmd", "/c", "start", f"harness {slug}", *tail]


def open_window(slug):
    try:
        subprocess.Popen(window_command(slug))
    except OSError as exc:
        print(f"could not open a window ({exc}); watch with: "
              f"python .harness/run_plan.py {slug} --watch")
        return False
    return True
