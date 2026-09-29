#!/usr/bin/env python3
"""Measure and compare the parts of pi harness wall time."""

import argparse
import csv
import json
import os
from pathlib import Path
import shutil
import socket
import statistics
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "harness-speed-test" / "latency.jsonl"
REPORT_PATH = ROOT / "harness-speed-test" / "LATENCY.md"
PI_LAUNCHER = Path.home() / ".pi" / "agent" / "bin" / "pi-launcher.js"
DEFAULT_MODEL = "opencode/space-bunny-free"
THINKING = "medium"
SHORT_PROMPT = "Reply OK"
LONG_PROMPT = "Write a 300-word explanation of HTTP caching."
PROMPT_SUFFIX = "Work in the current directory. Python. Do not ask questions; finish the whole task."
_OC_SESSION = {
    "permission": [
        {"permission": permission, "action": "deny", "pattern": "*"}
        for permission in ("question", "plan_enter", "plan_exit")
    ]
}


def pi_command(*args):
    node = shutil.which("node")
    if node is None:
        raise FileNotFoundError("node was not found on PATH")
    if not PI_LAUNCHER.is_file():
        raise FileNotFoundError(f"pi was not found at {PI_LAUNCHER}")
    return [node, str(PI_LAUNCHER), *args]


def opencode_command(*args):
    discovered = shutil.which("opencode")
    if discovered is None:
        raise FileNotFoundError("opencode was not found on PATH")
    discovered_path = Path(discovered)
    native = discovered_path.parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
    if native.exists():
        return [str(native), *args]
    if discovered_path.suffix.lower() == ".cmd":
        raise FileNotFoundError("opencode was found only as a .cmd wrapper")
    return [discovered, *args]


def _opencode_env(work_dir, config_dir):
    env = os.environ.copy()
    env["XDG_CONFIG_HOME"] = str(config_dir)
    env["PWD"] = str(work_dir)
    return env


def build_opencode_config(oc_tune, executor_prompt=""):
    """Build the opencode config used by tuning levels 2 through 4."""
    if oc_tune < 2:
        return None
    config = {
        "snapshot": False,
        "lsp": False,
        "formatter": False,
        "autoupdate": False,
        "share": "disabled",
        "agent": {
            "title": {"disable": True},
            "summary": {"disable": True},
        },
    }
    if oc_tune == 3:
        config["agent"]["lean"] = {
            "mode": "primary",
            "prompt": executor_prompt,
            "tools": {
                "todowrite": False,
                "todoread": False,
                "task": False,
                "webfetch": False,
                "websearch": False,
            },
        }
    if oc_tune == 4:
        config["permission"] = {
            "*": "allow",
            "question": "deny",
            "plan_enter": "deny",
            "plan_exit": "deny",
        }
    return config


def _write_opencode_config(config_dir, oc_tune):
    config = build_opencode_config(
        oc_tune, (ROOT / ".pi" / "executor.md").read_text(encoding="utf-8")
    )
    if config is None:
        return
    path = config_dir / "opencode" / "opencode.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _kill_process_tree(process):
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, check=False,
        )
    else:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def _start_opencode_server(work_dir, config_dir, oc_tune):
    """Start a warm server, returning its process, attach URL, and startup time."""
    _write_opencode_config(config_dir, oc_tune)
    port = _free_port()
    attach_url = f"http://127.0.0.1:{port}"
    env = _opencode_env(work_dir, config_dir)
    started = time.monotonic()
    process = subprocess.Popen(
        opencode_command("serve", "--port", str(port)), cwd=work_dir, env=env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    while True:
        if process.poll() is not None:
            raise RuntimeError(f"opencode serve exited with status {process.returncode}")
        try:
            with urllib.request.urlopen(attach_url, timeout=1):
                pass
            return process, attach_url, time.monotonic() - started
        except urllib.error.HTTPError:
            return process, attach_url, time.monotonic() - started
        except (urllib.error.URLError, TimeoutError):
            if time.monotonic() - started > 120:
                _kill_process_tree(process)
                raise TimeoutError("opencode serve did not answer HTTP within 120 seconds")
            time.sleep(0.1)


def _oc_http(url, path, body=None):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(
        f"{url}{path}", data=data, headers=headers,
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _oc_prompt_body(model, prompt):
    provider, api_model = _model_parts(model)
    return {
        "model": {"providerID": provider, "modelID": api_model},
        "variant": THINKING,
        "parts": [{"type": "text", "text": prompt}],
    }


def _oc_http_ask(url, model, prompt):
    session = _oc_http(url, "/session", _OC_SESSION)
    session_id = session["id"]
    response = _oc_http(
        url, f"/session/{session_id}/message", _oc_prompt_body(model, prompt)
    )
    if response["info"].get("error"):
        raise RuntimeError(response["info"]["error"])
    return response


def append_rows(rows):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATA_PATH.open("a", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":")) + "\n")


def _event_type(event):
    return event.get("type", "") if isinstance(event, dict) else ""


def summarize_trace(events):
    """Summarize timestamped pi events without modifying the event list."""
    if not events:
        raise ValueError("events must not be empty")

    t0 = events[0].get("t0", events[0]["t"])
    first_t = events[0]["t"]
    last_t = events[-1]["t"]
    assistant_start = None
    first_update = None
    turn_start = None
    model_wait_s = 0.0
    model_gen_s = 0.0
    turns = 0
    tool_starts = {}
    tool_s = 0.0
    tool_calls = 0

    for event in events:
        timestamp = event["t"]
        payload = event.get("e", {})
        kind = _event_type(payload)
        if kind == "turn_start":
            turn_start = timestamp
        elif kind == "message_start":
            if payload.get("message", {}).get("role") == "assistant":
                # pi emits message_start only once the first token arrives, so the
                # model's time-to-first-token is turn_start -> message_start
                if turn_start is not None:
                    model_wait_s += max(0.0, timestamp - turn_start)
                    turn_start = None
                assistant_start = timestamp
                first_update = None
        elif kind == "message_update" and assistant_start is not None:
            if first_update is None:
                first_update = timestamp
                model_wait_s += max(0.0, first_update - assistant_start)
        elif kind == "message_end":
            if payload.get("message", {}).get("role") == "assistant":
                if first_update is not None:
                    model_gen_s += max(0.0, timestamp - first_update)
                turns += 1
                assistant_start = None
                first_update = None
        elif kind == "tool_execution_start":
            call_id = payload.get("toolCallId")
            if call_id is not None:
                tool_starts.setdefault(call_id, timestamp)
                tool_calls += 1
        elif kind == "tool_execution_end":
            call_id = payload.get("toolCallId")
            if call_id in tool_starts:
                tool_s += max(0.0, timestamp - tool_starts.pop(call_id))

    startup_s = max(0.0, first_t - t0)
    total_s = max(0.0, last_t - t0)
    pi_gap_s = max(0.0, total_s - startup_s - model_wait_s - model_gen_s - tool_s)
    return {
        "startup_s": startup_s,
        "model_wait_s": model_wait_s,
        "model_gen_s": model_gen_s,
        "tool_s": tool_s,
        "total_s": total_s,
        "pi_gap_s": pi_gap_s,
        "turns": turns,
        "tool_calls": tool_calls,
    }


def summarize_opencode_trace(events):
    """Summarize stamped opencode events without modifying the event list."""
    if not events:
        raise ValueError("events must not be empty")

    t0 = events[0].get("t0", events[0]["t"])
    last_t = events[-1]["t"]
    model_gen_s = 0.0
    tool_s = 0.0
    turns = 0
    tool_calls = 0
    output_tokens = 0
    step_start = None
    step_tool_s = 0.0
    gap_s = 0.0
    last_finish = None

    for event in events:
        payload = event.get("e", {})
        kind = _event_type(payload)
        timestamp = payload.get("timestamp", event["t"] * 1000) / 1000
        part = payload.get("part", {})
        output_tokens += int(part.get("tokens", {}).get("output", 0) or 0)
        if kind == "step_start":
            if last_finish is not None:
                gap_s += max(0.0, timestamp - last_finish)
            step_start = timestamp
            step_tool_s = 0.0
        elif kind == "tool_use":
            tool_calls += 1
            timing = part.get("state", {}).get("time", {})
            if "start" in timing and "end" in timing:
                step_tool_s += max(0.0, (timing["end"] - timing["start"]) / 1000)
        elif kind == "step_finish" and step_start is not None:
            duration = max(0.0, timestamp - step_start)
            tool_s += step_tool_s
            model_gen_s += max(0.0, duration - step_tool_s)
            turns += 1
            step_start = None
            last_finish = timestamp

    if last_finish is not None:
        gap_s += max(0.0, last_t - last_finish)
    return {
        "startup_s": max(0.0, events[0]["t"] - t0),
        "model_wait_s": 0.0,
        "model_gen_s": model_gen_s,
        "tool_s": tool_s,
        "total_s": max(0.0, last_t - t0),
        "pi_gap_s": gap_s,
        "turns": turns,
        "tool_calls": tool_calls,
        "output_tokens": output_tokens,
    }


def harness_rows(runs_dir, label, model=DEFAULT_MODEL, harness="pi", oc_tune=0):
    """Convert completed harness stage timing into one row per stage."""
    runs_dir = Path(runs_dir)
    stages_csv = runs_dir.parent / "stages.csv"
    with stages_csv.open(newline="", encoding="utf-8-sig") as stream:
        csv_rows = list(csv.DictReader(stream))
    task = runs_dir.name
    results = []
    for run_dir in sorted(runs_dir.glob(f"{label}-*")):
        try:
            rep = int(run_dir.name[len(label) + 1:])
        except ValueError:
            continue
        stage_matches = {
            int(row["stage"]): row
            for row in csv_rows
            if row.get("arm") == label
            and row.get("task") == task
            and row.get("rep") == str(rep)
            and row.get("stage", "").isdigit()
        }
        for plan_dir in sorted((run_dir / ".harness" / "plans").glob("stage-*")):
            if not plan_dir.name[len("stage-"):].isdigit():
                continue
            stage = int(plan_dir.name[len("stage-"):])
            if stage not in stage_matches:
                continue
            metrics = []
            for path in sorted((plan_dir / "items").glob("*.metrics.json")):
                with path.open(encoding="utf-8") as stream:
                    metrics.append(json.load(stream))
            def total(key):
                return sum(float(item.get(key, 0) or 0) for item in metrics)

            stage_csv = stage_matches[stage]
            plan_s = float(stage_csv.get("plan_min", 0) or 0) * 60
            build_s = float(stage_csv.get("build_min", 0) or 0) * 60
            exec_s = total("exec_s")
            accept_s = total("accept_s")
            retry_s = total("retry_s")
            results.append({
                "kind": "harness",
                "harness": harness,
                "model": model,
                "oc_tune": oc_tune,
                "task": task,
                "label": label,
                "rep": rep,
                "stage": stage,
                "plan_s": plan_s,
                "build_s": build_s,
                "exec_s": exec_s,
                "accept_s": accept_s,
                "retry_s": retry_s,
                "runner_s": max(0.0, build_s - exec_s - accept_s - retry_s),
                "stage_wall_s": plan_s + build_s,
            })
    return results


def run_startup(n, model=DEFAULT_MODEL, harness="pi", oc_tune=0):
    rows = []
    with tempfile.TemporaryDirectory(prefix="latency-startup-") as work_name, \
            tempfile.TemporaryDirectory(prefix="latency-xdg-") as config_name:
        work_root = Path(work_name)
        config_dir = Path(config_name)
        server = None
        server_start_s = 0.0
        attach_url = None
        warmup_s = None
        if harness == "opencode" and oc_tune > 0:
            server, attach_url, server_start_s = _start_opencode_server(
                work_root, config_dir, oc_tune
            )
            if oc_tune == 4:
                warmup_started = time.monotonic()
                _oc_http_ask(attach_url, model, SHORT_PROMPT)
                warmup_s = time.monotonic() - warmup_started
        try:
            for index in range(n):
                work_dir = work_root / f"run-{index + 1}"
                work_dir.mkdir()
                if harness == "opencode" and oc_tune == 4:
                    started = time.monotonic()
                    _oc_http_ask(attach_url, model, SHORT_PROMPT)
                    exit_s = time.monotonic() - started
                    rows.append({
                        "kind": "startup",
                        "harness": harness,
                        "model": model,
                        "oc_tune": oc_tune,
                        "server_start_s": server_start_s,
                        "warmup_s": warmup_s,
                        "run": index + 1,
                        "version_s": None,
                        "first_line_s": None,
                        "first_finish_s": None,
                        "first_update_s": None,
                        "exit_s": exit_s,
                    })
                    continue
                if harness == "pi":
                    command = pi_command(
                        "-p", "--mode", "json", "--no-session", "--no-tools", "--no-extensions",
                        "--no-skills", "--no-context-files", "--no-prompt-templates", "--model",
                        model, "--thinking", THINKING, SHORT_PROMPT,
                    )
                    version_command = pi_command("--version")
                    env = None
                else:
                    command = opencode_command(
                        "run", "--pure", "--dir", str(work_dir), "-m", model,
                        "--variant", THINKING, "--format", "json",
                    )
                    if attach_url is not None:
                        command.extend(("--attach", attach_url))
                    if oc_tune == 3:
                        command.extend(("--agent", "lean"))
                    command.append(SHORT_PROMPT)
                    version_command = opencode_command("--version")
                    env = _opencode_env(work_root, config_dir)
                version_started = time.monotonic()
                subprocess.run(version_command, cwd=work_dir, env=env,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, check=True)
                version_s = time.monotonic() - version_started
                started = time.monotonic()
                process = subprocess.Popen(command, cwd=work_dir, env=env,
                                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.DEVNULL)
                first_line = first_finish = first_update = None
                assert process.stdout is not None
                for raw_line in process.stdout:
                    arrived = time.monotonic()
                    if first_line is None:
                        first_line = arrived
                    try:
                        payload = json.loads(raw_line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        continue
                    if harness == "opencode" and first_finish is None and payload.get("type") == "step_finish":
                        first_finish = arrived
                    if harness == "pi" and first_update is None and payload.get("type") == "message_update":
                        first_update = arrived
                exit_time = time.monotonic()
                if process.wait() != 0:
                    raise subprocess.CalledProcessError(process.returncode, command)
                rows.append({
                    "kind": "startup",
                    "harness": harness,
                    "model": model,
                    "oc_tune": oc_tune,
                    "server_start_s": server_start_s,
                    "run": index + 1,
                    "version_s": version_s,
                    "first_line_s": first_line - started if first_line is not None else None,
                    "first_finish_s": first_finish - started if first_finish is not None else None,
                    "first_update_s": first_update - started if first_update is not None else None,
                    "exit_s": exit_time - started,
                })
        finally:
            if server is not None:
                _kill_process_tree(server)
    return rows


def _model_parts(model):
    provider, separator, api_model = model.partition("/")
    if not separator or not provider or not api_model:
        raise ValueError("model must be in the form <provider>/<model>")
    return provider, api_model


def _direct_base_url(provider):
    urls = {
        "opencode": "https://opencode.ai/zen/v1",
        "openrouter": "https://openrouter.ai/api/v1",
    }
    if provider not in urls:
        raise ValueError(f"unsupported direct provider {provider!r}; choose opencode or openrouter")
    return urls[provider]


def _api_key(provider):
    completed = subprocess.run(
        pi_command("auth", "print-api-key", "--provider", provider),
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, check=True,
    )
    key = completed.stdout.strip()
    if not key:
        raise RuntimeError("pi returned an empty API key")
    return key


def _direct_request(key, prompt, prompt_name, index, model):
    provider, api_model = _model_parts(model)
    body = json.dumps({
        "model": api_model,
        "stream": True,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    request = urllib.request.Request(
        f"{_direct_base_url(provider)}/chat/completions", data=body,
        # the endpoint returns 403 for Python-urllib's default User-Agent
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "latency.py"},
        method="POST",
    )
    started = time.monotonic()
    first_token = None
    output = []
    chunks = 0
    with urllib.request.urlopen(request, timeout=1200) as response:
        for raw_line in response:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                payload = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = (payload.get("choices") or [{}])[0].get("delta", {})  # usage chunks have choices: []
            text = delta.get("content")
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if text or reasoning:
                chunks += 1
                if first_token is None:
                    first_token = time.monotonic()
            if text:
                output.append(text)
    total_s = time.monotonic() - started
    return {
        "kind": "direct",
        "harness": "pi",
        "model": model,
        "run": index,
        "prompt": prompt_name,
        "ttft_s": first_token - started if first_token is not None else None,
        "total_s": total_s,
        "output_chars": len("".join(output)),
        "chunks": chunks,
    }


def run_direct(n, model=DEFAULT_MODEL, harness="pi", oc_tune=0):
    provider, _ = _model_parts(model)
    key = _api_key(provider)
    rows = []
    for index in range(1, n + 1):
        for prompt, prompt_name in ((SHORT_PROMPT, "short"), (LONG_PROMPT, "long")):
            row = _direct_request(key, prompt, prompt_name, index, model)
            row["oc_tune"] = oc_tune
            row["server_start_s"] = 0.0
            rows.append(row)
    return rows


def task_prompt(task_dir):
    source = task_dir / "spec.md"
    if not source.is_file():
        source = task_dir / "plan" / "plan.md"
    if not source.is_file():
        raise FileNotFoundError(f"no spec.md or plan/plan.md in {task_dir}")
    return f"{source.read_text(encoding='utf-8')}\n\n{PROMPT_SUFFIX}"


def _bus_to_run_event(event):
    if not isinstance(event, dict) or event.get("type") != "message.part.updated":
        return None
    properties = event.get("properties", {})
    part = properties.get("part", {})
    part_type = part.get("type")
    if part_type not in ("step-start", "step-finish"):
        if not (part_type == "tool"
                and part.get("state", {}).get("status") == "completed"):
            return None
    return {"type": {
        "step-start": "step_start",
        "tool": "tool_use",
        "step-finish": "step_finish",
    }[part_type], "timestamp": properties.get("time"), "part": part}


def _read_oc_events(url, events, connected, response_holder):
    try:
        with urllib.request.urlopen(f"{url}/event", timeout=1800) as response:
            response_holder.append(response)
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if not data:
                    continue
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                item = {"t": time.monotonic(), "e": payload}
                events.append(item)
                if payload.get("type") == "server.connected":
                    connected.set()
    except Exception:
        pass


def run_trace(name, model=DEFAULT_MODEL, harness="pi", oc_tune=0):
    task_dir = ROOT / ".harness" / "bench" / "tasks" / name
    prompt = task_prompt(task_dir)
    work_dir = Path(tempfile.mkdtemp(prefix=f"latency-{name}-"))
    seed = task_dir / "seed"
    if seed.is_dir():
        shutil.copytree(seed, work_dir, dirs_exist_ok=True)
    trace_path = work_dir / "trace.jsonl"
    server = None
    server_start_s = 0.0
    warmup_s = None
    with tempfile.TemporaryDirectory(prefix="latency-xdg-") as config_name:
        config_dir = Path(config_name)
        try:
            if harness == "pi":
                command = pi_command(
                    "-p", "--mode", "json", "--no-session", "-e",
                    str(ROOT / ".pi/extensions/deny-list.ts"), "--append-system-prompt",
                    str(ROOT / ".pi/executor.md"), "--model", model, "--thinking", THINKING, prompt,
                )
                env = None
            else:
                if oc_tune > 0:
                    server, attach_url, server_start_s = _start_opencode_server(
                        work_dir, config_dir, oc_tune
                    )
                    if oc_tune == 4:
                        warmup_started = time.monotonic()
                        _oc_http_ask(attach_url, model, SHORT_PROMPT)
                        warmup_s = time.monotonic() - warmup_started

            if harness == "opencode" and oc_tune == 4:
                bus_events = []
                connected = threading.Event()
                response_holder = []
                reader = threading.Thread(
                    target=_read_oc_events,
                    args=(attach_url, bus_events, connected, response_holder),
                    daemon=True,
                )
                reader.start()
                if not connected.wait(10):
                    raise TimeoutError("opencode event stream did not connect within 10 seconds")
                session = _oc_http(attach_url, "/session", _OC_SESSION)
                session_id = session["id"]
                spawned = time.monotonic()
                _oc_http(
                    attach_url, f"/session/{session_id}/prompt_async",
                    _oc_prompt_body(model, prompt),
                )
                deadline = time.monotonic() + 1800
                while time.monotonic() < deadline:
                    if any(
                        item["e"].get("type", "").startswith(("question.asked", "permission.asked"))
                        and item["e"].get("properties", {}).get("sessionID") == session_id
                        for item in bus_events
                    ):
                        raise RuntimeError("opencode session blocked on question/permission")
                    if any(
                        item["e"].get("type") == "session.idle"
                        and item["e"].get("properties", {}).get("sessionID") == session_id
                        for item in bus_events
                    ):
                        break
                    time.sleep(0.05)
                else:
                    raise TimeoutError("opencode session did not become idle within 1800 seconds")
                for response in response_holder:
                    response.close()
                events = []
                for bus_event in bus_events:
                    if bus_event["e"].get("properties", {}).get("sessionID") != session_id:
                        continue
                    run_event = _bus_to_run_event(bus_event["e"])
                    if run_event is None:
                        continue
                    item = {"t": bus_event["t"], "e": run_event}
                    if not events:
                        item["t0"] = spawned
                    events.append(item)
                    with trace_path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(item, separators=(",", ":")) + "\n")
            else:
                if harness == "opencode":
                    command = opencode_command(
                        "run", "--pure", "--dir", str(work_dir), "-m", model,
                        "--variant", THINKING, "--format", "json",
                    )
                    if server is not None:
                        command.extend(("--attach", attach_url))
                    if oc_tune == 3:
                        command.extend(("--agent", "lean"))
                    command.extend(("--auto", prompt))
                    env = _opencode_env(work_dir, config_dir)
                spawned = time.monotonic()
                process = subprocess.Popen(command, cwd=work_dir, env=env, stdin=subprocess.DEVNULL,
                                           stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                events = []
                assert process.stdout is not None
                for raw_line in process.stdout:
                    timestamp = time.monotonic()
                    try:
                        payload = json.loads(raw_line)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        if harness == "pi":
                            continue
                        payload = {"type": "text", "text": raw_line.decode("utf-8", errors="replace").rstrip()}
                    item = {"t": timestamp, "e": payload}
                    if not events:
                        item["t0"] = spawned
                    events.append(item)
                    with trace_path.open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps(item, separators=(",", ":")) + "\n")
                if process.wait() != 0:
                    raise subprocess.CalledProcessError(process.returncode, command)
        finally:
            if server is not None:
                _kill_process_tree(server)
    row = {"kind": "trace", "harness": harness, "model": model, "oc_tune": oc_tune,
           "server_start_s": server_start_s, "task": name, "trace": str(trace_path)}
    if warmup_s is not None:
        row["warmup_s"] = warmup_s
    row.update(summarize_trace(events) if harness == "pi" else summarize_opencode_trace(events))
    return [row]


def read_rows():
    if not DATA_PATH.exists():
        return []
    with DATA_PATH.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def _numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _format(value):
    return f"{value:.3f}" if isinstance(value, float) else str(value)


def _percent(value, total):
    return f"{100.0 * value / total:.1f}%" if total > 0 else "0.0%"


def build_report(rows):
    def model_of(row):
        return row.get("model", DEFAULT_MODEL)

    def harness_of(row):
        return row.get("harness", "pi")

    def oc_tune_of(row):
        return row.get("oc_tune", 0)

    lines = ["# Latency measurements", ""]
    for kind in ("harness", "startup", "direct", "trace"):
        selected = [row for row in rows if row.get("kind") == kind]
        if not selected:
            continue
        keys = []
        for row in selected:
            for key in row:
                if key not in ("kind", "harness", "model", "oc_tune") and key not in keys:
                    keys.append(key)
        numeric_keys = [key for key in keys if any(_numeric(row.get(key)) for row in selected)]
        lines.extend((f"## {kind.title()}", ""))
        groups = sorted({(harness_of(row), model_of(row), oc_tune_of(row)) for row in selected})
        lines.extend(("| Harness | Model | OC Tune | Metric | Median |",
                      "| --- | --- | ---: | --- | ---: |"))
        for group_harness, model, oc_tune in groups:
            group_rows = [row for row in selected
                          if harness_of(row) == group_harness
                          and model_of(row) == model and oc_tune_of(row) == oc_tune]
            for key in numeric_keys:
                values = [float(row[key]) for row in group_rows if _numeric(row.get(key))]
                if values:
                    median = _format(statistics.median(values))
                    if kind == "harness":
                        lines.append(f"| {group_harness} | {model} | {oc_tune} | {key} | {median} |")
                    else:
                        lines.append(f"| {group_harness} | {model} | {oc_tune} | {key} | {median} |")
        lines.append("")

    lines.extend(("## Share of wall time", "",
                  "| Harness | Model | OC Tune | Kind | Item | Share |",
                  "| --- | --- | ---: | --- | --- | ---: |"))
    for row in rows:
        if row.get("kind") != "trace":
            continue
        total = float(row.get("total_s", 0) or 0)
        model = model_of(row)
        item = f"trace:{row.get('task', '')}"
        for key, label in (("startup_s", f"{harness_of(row)} startup"),
                           ("model_wait_s", "model wait"),
                           ("model_gen_s", "model generation"), ("tool_s", "tool execution"),
                           ("pi_gap_s", "harness gap")):
            lines.append(f"| {harness_of(row)} | {model} | {oc_tune_of(row)} | {item} | {label} | {_percent(float(row.get(key, 0) or 0), total)} |")
    for row in rows:
        if row.get("kind") != "harness":
            continue
        total = float(row.get("stage_wall_s", 0) or 0)
        item = f"harness:stage {row.get('stage', '')}"
        for key, label in (("plan_s", "planning"), ("exec_s", "execution"),
                           ("accept_s", "acceptance"), ("runner_s", "runner overhead")):
            lines.append(f"| {harness_of(row)} | {model_of(row)} | {oc_tune_of(row)} | {item} | {label} | {_percent(float(row.get(key, 0) or 0), total)} |")

    candidates = []
    for kind, fields in (
        ("harness", (("plan_s", "Sonnet planning"), ("exec_s", "agent execution"),
                      ("accept_s", "acceptance"), ("runner_s", "runner overhead"))),
        ("startup", (("version_s", "pi process overhead"),)),
        ("direct", (("ttft_s", "model/router latency"),)),
        ("trace", (("startup_s", "pi startup"), ("model_wait_s", "model wait"),
                   ("model_gen_s", "model generation"), ("tool_s", "tool execution"),
                   ("pi_gap_s", "pi gap"))),
    ):
        selected = [row for row in rows if row.get("kind") == kind]
        for key, label in fields:
            values = [float(row[key]) for row in selected if _numeric(row.get(key))]
            if values:
                candidates.append((statistics.median(values), label))
    if candidates:
        lines.extend(("", f"**Verdict:** {max(candidates)[1]} is the largest measured component."))
    else:
        lines.extend(("", "**Verdict:** no measurements available."))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--harness", choices=("pi", "opencode"), default="pi",
                        help="harness CLI to measure (default: pi)")
    parser.add_argument("--oc-tune", type=int, choices=(0, 1, 2, 3, 4), default=0,
                        help="opencode tuning level (default: 0)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="model route (provider/model)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    harness = subparsers.add_parser("harness")
    harness.add_argument("--runs", type=Path, required=True)
    harness.add_argument("--label", required=True)
    startup = subparsers.add_parser("startup")
    startup.add_argument("--n", type=int, default=10)
    direct = subparsers.add_parser("direct")
    direct.add_argument("--n", type=int, default=10)
    trace = subparsers.add_parser("trace")
    trace.add_argument("--task", required=True)
    subparsers.add_parser("report")
    args = parser.parse_args(argv)

    if args.command == "harness":
        if args.oc_tune == 4:
            parser.error("--oc-tune 4 supports startup and trace only")
        rows = harness_rows(args.runs, args.label, args.model, args.harness, args.oc_tune)
    elif args.command == "startup":
        if args.n < 1:
            parser.error("--n must be at least 1")
        rows = run_startup(args.n, args.model, args.harness, args.oc_tune)
    elif args.command == "direct":
        try:
            _model_parts(args.model)
            _direct_base_url(_model_parts(args.model)[0])
        except ValueError as error:
            parser.error(str(error))
        if args.n < 1:
            parser.error("--n must be at least 1")
        rows = run_direct(args.n, args.model, args.harness, args.oc_tune)
    elif args.command == "trace":
        rows = run_trace(args.task, args.model, args.harness, args.oc_tune)
    else:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(build_report(read_rows()), encoding="utf-8")
        return 0
    append_rows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
