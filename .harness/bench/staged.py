"""Run and score a staged benchmark arm in one persistent Claude session."""
import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".harness"))
import envfile  # noqa: E402
envfile.load_env()

import bench


def _load_run_plan():
    spec = importlib.util.spec_from_file_location("run_plan_lab", bench.ROOT / ".harness" / "run_plan.py")
    rp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rp)
    return rp


rp = _load_run_plan()
from runner import planner as rp_planner  # noqa: E402  (run_plan.py put .harness on sys.path)

COLUMNS = (
    "task", "arm", "rep", "stage", "stage_usd", "cum_usd", "main_input",
    "main_cache_write", "main_cache_read", "main_output", "main_usd_est",
    "ctx_end_tokens", "compactions", "planner_runs", "planner_input",
    "planner_cache_write", "planner_cache_read", "planner_output",
    "planner_usd_est", "exec_input", "exec_output", "exec_cache_read",
    "retries", "rate_limit_waits", "plan_min", "build_min", "verify_min",
    "stage_min", "cum_min", "stage_passed", "stage_failed", "all_passed",
    "all_failed", "note",
)

STEP_COLUMNS = (
    "task", "arm", "rep", "stage", "step", "seconds", "fresh", "cache_write",
    "cache_read", "output", "usd", "result", "note",
)

OLD_PLANNER_REV = "1587d23"

K_PLANNER_FLAGS = [
    "--strict-mcp-config", "--setting-sources",
    "project,local", "--tools", "Read,Grep,Glob,Write,Bash",
]


def parse_score(text, n):
    counts = {"all_passed": 0, "all_failed": 0, "stage_passed": 0, "stage_failed": 0}
    stage_file = f"test_s{n}.py"
    for line in text.splitlines():
        line = line.lstrip()
        if line.startswith("PASSED "):
            kind = "passed"
        elif line.startswith("FAILED "):
            kind = "failed"
        elif line.startswith("ERROR "):
            kind = "failed"
        else:
            continue
        counts["all_" + kind] += 1
        if stage_file in line:
            counts["stage_" + kind] += 1
    return counts


def _utc_timestamp(value):
    ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


def transcript_usage(lines, start, end, prices):
    lines = list(lines)
    last = {}
    for line in lines:
        try:
            entry = json.loads(line)
        except (TypeError, ValueError):
            continue
        message = entry.get("message")
        if not isinstance(message, dict) or not message.get("usage"):
            continue
        timestamp = entry.get("timestamp")
        if not timestamp:
            continue
        try:
            timestamp = _utc_timestamp(timestamp)
        except (TypeError, ValueError):
            continue
        request_id = entry.get("requestId")
        last[request_id] = (message["usage"], timestamp, message.get("model"))

    result = {
        "main_input": 0, "main_cache_write": 0, "main_cache_read": 0,
        "main_output": 0, "main_usd_est": 0.0, "ctx_end_tokens": 0,
        "compactions": 0,
    }
    last_usage = None
    for line in lines:
        try:
            entry = json.loads(line)
        except (TypeError, ValueError):
            continue
        timestamp = entry.get("timestamp")
        try:
            timestamp = _utc_timestamp(timestamp) if timestamp else None
        except (TypeError, ValueError):
            timestamp = None
        if timestamp is not None and start <= timestamp <= end:
            if entry.get("subtype") == "compact_boundary" or entry.get("isCompactSummary") is True:
                result["compactions"] += 1

    for usage, timestamp, model in sorted(last.values(), key=lambda item: item[1]):
        if not start <= timestamp <= end:
            continue
        input_tokens = usage.get("input_tokens", 0) or 0
        cache_read = usage.get("cache_read_input_tokens", 0) or 0
        cache_creation = usage.get("cache_creation") or {}
        write_5m = cache_creation.get("ephemeral_5m_input_tokens", 0) or 0
        write_1h = cache_creation.get("ephemeral_1h_input_tokens", 0) or 0
        if not (write_5m or write_1h):
            write_5m = usage.get("cache_creation_input_tokens", 0) or 0
        output_tokens = usage.get("output_tokens", 0) or 0
        result["main_input"] += input_tokens
        result["main_cache_write"] += write_5m + write_1h
        result["main_cache_read"] += cache_read
        result["main_output"] += output_tokens
        price = prices.get(model)
        if price:
            pin, pout, pread = price
            result["main_usd_est"] += (
                input_tokens * pin + output_tokens * pout + cache_read * pread
                + (write_5m * 1.25 + write_1h * 2.0) * pin
            ) / 1e6
        last_usage = usage
    if last_usage is not None:
        cache_creation = last_usage.get("cache_creation") or {}
        write_5m = cache_creation.get("ephemeral_5m_input_tokens", 0) or 0
        write_1h = cache_creation.get("ephemeral_1h_input_tokens", 0) or 0
        if not (write_5m or write_1h):
            write_5m = last_usage.get("cache_creation_input_tokens", 0) or 0
        result["ctx_end_tokens"] = (
            (last_usage.get("input_tokens", 0) or 0) + cache_read
            + write_5m + write_1h
        )
    return result


def csv_line(row):
    return ",".join(str(row.get(column, "")).replace(",", ";") for column in COLUMNS)


def step_line(row):
    return ",".join(str(row.get(column, "")).replace(",", ";") for column in STEP_COLUMNS)


def _append_step(row):
    path = bench.BENCH / "runs" / "steps.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(",".join(STEP_COLUMNS) + "\n", encoding="utf-8")
    with path.open("a", encoding="utf-8") as output:
        output.write(step_line(row) + "\n")


def claude_usage(data):
    usage = data.get("modelUsage") or {}
    return {
        "seconds": round(data.get("_s", 0) or 0, 1),
        "fresh": sum(model.get("inputTokens", 0) or 0 for model in usage.values()),
        "cache_write": sum(
            model.get("cacheCreationInputTokens", 0) or 0 for model in usage.values()
        ),
        "cache_read": sum(
            model.get("cacheReadInputTokens", 0) or 0 for model in usage.values()
        ),
        "output": sum(model.get("outputTokens", 0) or 0 for model in usage.values()),
        "usd": data.get("total_cost_usd", 0) or 0,
    }


def task_step_rows(plan_dir):
    items = Path(plan_dir) / "items"
    if not items.exists():
        return []
    paths = sorted(
        items.glob("T*.metrics.json"),
        key=lambda path: int(re.fullmatch(r"T(\d+)\.metrics\.json", path.name).group(1)),
    )
    rows = []
    for path in paths:
        task_id = path.name.removesuffix(".metrics.json")
        try:
            metrics = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        tokens = metrics.get("tokens") or {}
        rows.append({
            "step": f"{task_id}.exec", "seconds": metrics.get("exec_s", 0) or 0,
            "fresh": tokens.get("input", 0) or 0,
            "cache_read": tokens.get("cache_read", 0) or 0,
            "output": tokens.get("output", 0) or 0, "usd": tokens.get("cost", 0) or 0,
            "result": metrics.get("result", ""),
        })
        rows.append({
            "step": f"{task_id}.accept", "seconds": metrics.get("accept_s", 0) or 0,
        })
        if (metrics.get("retry_s", 0) or 0) > 0:
            rows.append({
                "step": f"{task_id}.retry", "seconds": metrics.get("retry_s", 0) or 0,
            })
    return rows


def _write_state(path, sid, next_stage, cum_usd, cum_min):
    path.write_text(json.dumps({
        "sid": str(sid) if sid else None,
        "next_stage": next_stage,
        "cum_usd": cum_usd,
        "cum_min": cum_min,
    }), encoding="utf-8")


def _fresh_worktree(task, arm, rep, label=None):
    wt = bench.make_worktree(task, label or arm, rep, copy_plan=False, overlay_name=arm)
    task_dir = bench.BENCH / "tasks" / task
    seed_file = task_dir / "SEED.md"
    if seed_file.exists():
        for line in seed_file.read_text(encoding="utf-8").splitlines():
            match = re.fullmatch(r"\s*seed:\s*(\S.*?)\s*", line)
            if match:
                shutil.copytree(
                    task_dir / match.group(1), wt, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("node_modules", ".next"),
                )
                break
    if (wt / "package-lock.json").exists():
        subprocess.run("npm ci --no-audit --no-fund", cwd=wt, shell=True,
                       check=True, timeout=900)

    spec_dir = wt / "spec"
    spec_dir.mkdir(exist_ok=True)
    shutil.copy2(task_dir / "spec.md", spec_dir / "spec.md")
    (spec_dir / "stages").mkdir(exist_ok=True)
    for lab_test in ("test_build_map.py", "test_staged.py"):
        (wt / "tests" / lab_test).unlink(missing_ok=True)
    if arm in ("J", "J0", "K"):
        planner = wt / ".claude" / "agents" / "planner.md"
        text = planner.read_text(encoding="utf-8")
        if arm in ("J", "J0"):  # baseline arms keep the pre-contract planner (spec-test last task)
            text = subprocess.run(["git", "show", f"{OLD_PLANNER_REV}:.claude/agents/planner.md"],
                                  cwd=bench.ROOT, capture_output=True, text=True, check=True).stdout
        planner.write_text(re.sub(r"(?m)^model: opus$", "model: sonnet", text), encoding="utf-8")
    if arm in ("J0", "K"):
        (wt / ".harness" / "build_map.py").unlink()
    subprocess.run(["git", "init", "-q"], cwd=wt, check=True)
    with (wt / ".gitignore").open("a", encoding="utf-8") as gitignore:
        gitignore.write(
            "\n__pycache__/\n.pytest_cache/\n.harness/plans/*/logs/\n"
            ".harness/metrics.jsonl\n_hidden_tests/\ndata/\n_bench_state.json\nstage_runs/\n"
        )
    if arm == "J":
        subprocess.run([sys.executable, ".harness/build_map.py"], cwd=wt, check=True)
    _commit(wt, "stage-0")
    return wt


def _commit(wt, message):
    subprocess.run(["git", "add", "-A"], cwd=wt)
    subprocess.run(
        ["git", "-c", "user.name=bench", "-c", "user.email=bench@local",
         "commit", "-qm", message], cwd=wt,
    )


def _claude_call(prompt, wt, sid, step, stage, note):
    # Skip user plugins, hooks and MCP so the bench measures the arm, not this machine's setup.
    extra = ["--setting-sources", "project,local", "--strict-mcp-config"]
    extra += ["--resume", sid] if sid else []
    data = bench._claude(prompt, wt, "sonnet", 5400, extra)
    stage_runs = wt / "stage_runs"
    stage_runs.mkdir(exist_ok=True)
    (stage_runs / f"s{stage}_{step}.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
    note_add = f"{step} error; " if data.get("is_error") else ""
    return data, data.get("session_id") or sid, data.get("_s", 0) / 60, note_add


def planner_prompt(wt):
    text = (Path(wt) / ".claude" / "agents" / "planner.md").read_text(encoding="utf-8")
    return re.sub(r"\A---.*?---\s*", "", text, count=1, flags=re.S).strip()


def _planner_call(wt, stage):
    prompt = (
        f"Plan slug stage-{stage}: spec/spec.md and spec/stages/s{stage}.md. "
        "Plan this stage only; earlier stages exist and must keep working."
    )
    os.environ["CLAUDE_CODE_EFFORT_LEVEL"] = "medium"
    data = bench._claude(
        prompt, wt, "sonnet", 5400,
        ["--append-system-prompt", planner_prompt(wt), *K_PLANNER_FLAGS],
    )
    stage_runs = wt / "stage_runs"
    stage_runs.mkdir(exist_ok=True)
    (stage_runs / f"s{stage}_plan.json").write_text(
        json.dumps(data, indent=2), encoding="utf-8"
    )
    return data


def _planner_swap_call(wt, stage, backend):
    """Arm K with HARNESS_PLANNER: the neutral runner/planner.py writes the plan instead of
    a Claude planner call. It resolves paths and snapshots guards against the cwd, so run it
    from the worktree."""
    here = os.getcwd()
    os.chdir(wt)
    try:
        return rp_planner.run_planner(f"stage-{stage}", f"spec/stages/s{stage}.md",
                                      ".harness/plans", backend)
    finally:
        os.chdir(here)


def _run_plan(wt, slug):
    started = time.monotonic()
    try:
        result = subprocess.run(
            [sys.executable, ".harness/run_plan.py", slug,
             *os.environ.get("HARNESS_RUNNER_FLAGS", "").split()],  # e.g. "--executor claude --executor-model haiku"
            cwd=wt, capture_output=True, text=True, stdin=subprocess.DEVNULL,
            timeout=10800,
        )
        rc = result.returncode
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired as exc:
        rc = 124
        output = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
    return rc, output, time.monotonic() - started


def _score(wt, task, stage, note):
    hidden = bench.BENCH / "tasks" / task / "hidden_tests"
    destination = wt / "_hidden_tests"
    destination.mkdir(exist_ok=True)
    files = [hidden / "conftest.py"] + [hidden / f"test_s{i}.py" for i in range(1, stage + 1)]
    for source in files:
        if source.exists():
            shutil.copy2(source, destination / source.name)
    command = [
        sys.executable, "-m", "pytest", "_hidden_tests", "-q", "-rA",
        "-p", "no:cacheprovider",
    ]
    timed_out = False
    note_add = ""
    try:
        result = subprocess.run(command, cwd=wt, capture_output=True, text=True,
                                timeout=1800)
        output = result.stdout + result.stderr
        returncode = result.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output += "\npytest timed out\n"
        returncode = 1
        timed_out = True
        note_add = "score timed out; "
    counts = parse_score(output, stage)
    if timed_out:
        counts = {"all_passed": 0, "all_failed": 1,
                  "stage_passed": 0, "stage_failed": 1}
    elif not any(line.lstrip().startswith(("PASSED ", "FAILED ", "ERROR "))
                 for line in output.splitlines()) and returncode != 0:
        counts["all_failed"] = counts["stage_failed"] = 1
        note_add = "score crashed; "
    (wt / "stage_runs" / f"s{stage}_score.txt").write_text(output, encoding="utf-8")
    shutil.rmtree(destination)
    return counts, note_add


def _planner_usage(wt, stage):
    counts = {
        "planner_runs": 0, "planner_input": 0, "planner_cache_write": 0,
        "planner_cache_read": 0, "planner_output": 0, "planner_usd_est": 0.0,
    }
    slug = f"stage-{stage}"
    for run in rp.claude_agent_runs(project=wt):
        if run.get("agent") == "planner" and run.get("slug") == slug:
            counts["planner_runs"] += 1
            for source, destination in (
                ("input", "planner_input"), ("cache_write", "planner_cache_write"),
                ("cache_read", "planner_cache_read"), ("output", "planner_output"),
                ("cost", "planner_usd_est"),
            ):
                counts[destination] += run.get(source, 0) or 0
    return counts


def _executor_usage(wt, stage):
    counts = {"exec_input": 0, "exec_output": 0, "exec_cache_read": 0,
              "retries": 0, "rate_limit_waits": 0}
    metrics = wt / ".harness" / "metrics.jsonl"
    slug = f"stage-{stage}"
    if metrics.exists():
        for line in metrics.read_text(encoding="utf-8").splitlines():
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if record.get("slug") != slug:
                continue
            tokens = record.get("tokens") or {}
            counts["exec_input"] += tokens.get("input", 0) or 0
            counts["exec_output"] += tokens.get("output", 0) or 0
            counts["exec_cache_read"] += tokens.get("cache_read", 0) or 0
            counts["retries"] += (record.get("attempts", 1) or 1) - 1
    logs = wt / ".harness" / "plans" / slug / "logs"
    if logs.exists():
        for log in logs.glob("*.log"):
            counts["rate_limit_waits"] += len(re.findall(
                r"rate.?limit|too many requests|\b429\b",
                log.read_text(encoding="utf-8", errors="replace"), re.I,
            ))
    return counts


def run(task, arm, rep=1, continue_run=False, stages=None):
    task_dir = bench.BENCH / "tasks" / task
    stage_paths = sorted(
        task_dir.glob("stages/s*.md"),
        key=lambda path: int(re.fullmatch(r"s(\d+)\.md", path.name).group(1)),
    )
    if stages is not None:
        stage_paths = stage_paths[:stages]

    label = os.environ.get("HARNESS_ARM_LABEL", arm)
    if continue_run:
        wt = bench.worktree_path(task, label, rep)
        state_path = wt / "_bench_state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        wt = _fresh_worktree(task, arm, rep, label)
        state_path = wt / "_bench_state.json"
        state = {"sid": None, "next_stage": 1, "cum_usd": 0.0, "cum_min": 0.0}
        _write_state(state_path, state["sid"], state["next_stage"], state["cum_usd"], state["cum_min"])

    if arm in ("J", "J0", "K") and state["next_stage"] == 1 and not continue_run:
        old_cwd = os.getcwd()
        os.chdir(wt)
        try:
            if not rp.quota_ok(timeout=150):
                rp.wait_for_quota(str(wt / "quota_gate.log"))
        finally:
            os.chdir(old_cwd)

    sid = state.get("sid")
    build_broken = False
    for stage_path in stage_paths:
        stage = int(stage_path.stem[1:])
        if stage < state["next_stage"]:
            continue
        stage_spec = wt / "spec" / "stages" / f"s{stage}.md"
        stage_spec.parent.mkdir(exist_ok=True)
        shutil.copy2(stage_path, stage_spec)
        note = ""
        calls_usd = 0.0
        plan_min = build_min = verify_min = 0.0
        first_call = None
        last_call = None

        def call(prompt, step):
            nonlocal sid, first_call, last_call, note
            if first_call is None:
                first_call = datetime.now(timezone.utc)
            data, sid, minutes, note_add = _claude_call(
                prompt, wt, sid, step, stage, note
            )
            note += note_add
            _append_step({
                "task": task, "arm": label, "rep": rep, "stage": stage, "step": step,
                **claude_usage(data), "result": "error" if data.get("is_error") else "",
                "note": note,
            })
            last_call = datetime.now(timezone.utc)
            return data, minutes

        if arm == "PURE":
            data, build_min = call(
                f"Stage {stage}: build spec/stages/s{stage}.md now, following CLAUDE.md.",
                "build",
            )
            calls_usd += data.get("total_cost_usd", 0) or 0
        elif arm == "K":
            swap = os.environ.get("HARNESS_PLANNER")
            if swap and swap != "claude":
                swapped = _planner_swap_call(wt, stage, swap)
                tokens = swapped["tokens"]
                cost = tokens.get("cost") or 0.0
                plan_min = swapped["seconds"] / 60
                plan_usage = {"seconds": swapped["seconds"], "usd": cost,
                              "fresh": tokens["input"], "cache_write": 0,
                              "cache_read": tokens["cache_read"], "output": tokens["output"]}
                calls_usd += cost
                _append_step({
                    "task": task, "arm": label, "rep": rep, "stage": stage,
                    "step": "plan", **plan_usage,
                    "result": "" if swapped["lint_ok"] else "error",
                })
            else:
                plan_data = _planner_call(wt, stage)
                plan_usage = claude_usage(plan_data)
                plan_min = plan_usage["seconds"] / 60
                calls_usd += plan_usage["usd"]
                _append_step({
                    "task": task, "arm": label, "rep": rep, "stage": stage,
                    "step": "plan", **plan_usage,
                    "result": "error" if plan_data.get("is_error") else "",
                })
            plan_dir = wt / ".harness" / "plans" / f"stage-{stage}"
            tasks_file = plan_dir / "tasks.json"
            if tasks_file.exists():
                rc, runner_output, build_seconds = _run_plan(wt, f"stage-{stage}")
                build_min = build_seconds / 60
                _append_step({
                    "task": task, "arm": label, "rep": rep, "stage": stage,
                    "step": "build", "seconds": build_seconds,
                })
                failed = rc != 0
                if not failed:
                    for metrics_path in plan_dir.joinpath("items").glob("T*.metrics.json"):
                        try:
                            if json.loads(metrics_path.read_text(encoding="utf-8")).get("result") != "pass":
                                failed = True
                                break
                        except (OSError, ValueError):
                            failed = True
                            break
                if failed:
                    rerun_rc, rerun_output, rerun_seconds = _run_plan(wt, f"stage-{stage}")
                    rc = rerun_rc
                    runner_output = rerun_output
                    verify_min = rerun_seconds / 60
                    _append_step({
                        "task": task, "arm": label, "rep": rep, "stage": stage,
                        "step": "rerun", "seconds": rerun_seconds, "note": "rerun; ",
                    })
                for task_row in task_step_rows(plan_dir):
                    _append_step({
                        "task": task, "arm": label, "rep": rep, "stage": stage,
                        **task_row,
                    })
            else:
                rc = -1
                runner_output = ""
                note += "no plan; "
            runs = wt / "stage_runs"
            runs.mkdir(exist_ok=True)
            (runs / f"s{stage}_runner.txt").write_text(runner_output, encoding="utf-8")
            _append_step({
                "task": task, "arm": label, "rep": rep, "stage": stage,
                "step": "verify", "seconds": 0,
            })
            summary_path = plan_dir / "SUMMARY.md"
            if summary_path.exists() and "BUILD: fail" in summary_path.read_text(encoding="utf-8"):
                build_broken = True
                note += "build failed; "
        else:
            data, plan_min = call(
                f"PLAN stage-{stage}: spec/stages/s{stage}.md. Follow the PLAN step in CLAUDE.md.",
                "plan",
            )
            calls_usd += data.get("total_cost_usd", 0) or 0
            plan_dir = wt / ".harness" / "plans" / f"stage-{stage}"
            tasks_file = plan_dir / "tasks.json"
            if tasks_file.exists():
                rc, runner_output, build_seconds = _run_plan(wt, f"stage-{stage}")
                build_min = build_seconds / 60
                _append_step({
                    "task": task, "arm": label, "rep": rep, "stage": stage,
                    "step": "build", "seconds": build_seconds,
                })
                for task_row in task_step_rows(plan_dir):
                    _append_step({
                        "task": task, "arm": label, "rep": rep, "stage": stage,
                        **task_row,
                    })
            else:
                rc = -1
                runner_output = ""
                note += "no plan; "
            runs = wt / "stage_runs"
            runs.mkdir(exist_ok=True)
            (runs / f"s{stage}_runner.txt").write_text(runner_output, encoding="utf-8")
            data, verify_min = call(
                f"VERIFY stage-{stage}: the runner exited {rc}. Last lines:\n"
                f"{runner_output[-1500:]}\nFollow the VERIFY step in CLAUDE.md.",
                "verify",
            )
            calls_usd += data.get("total_cost_usd", 0) or 0

        (wt / "stage_runs").mkdir(exist_ok=True)
        _commit(wt, f"stage-{stage}")
        scores, note_add = _score(wt, task, stage, note)
        note += note_add

        usage = {
            "main_input": 0, "main_cache_write": 0, "main_cache_read": 0,
            "main_output": 0, "main_usd_est": 0.0, "ctx_end_tokens": 0,
            "compactions": 0,
        }
        if sid:
            transcripts = list((Path.home() / ".claude" / "projects").glob(
                f"*/{sid}.jsonl"
            ))
            if transcripts:
                lines = transcripts[0].read_text(encoding="utf-8", errors="replace").splitlines()
                usage = transcript_usage(lines, first_call, last_call, rp.PRICES)
            else:
                note += "no transcript; "

        extras = _planner_usage(wt, stage) if arm in ("J", "J0") else {
            "planner_runs": 0, "planner_input": 0, "planner_cache_write": 0,
            "planner_cache_read": 0, "planner_output": 0, "planner_usd_est": 0.0,
        }
        if arm == "K":
            extras = {
                "planner_runs": 1,
                "planner_input": plan_usage["fresh"],
                "planner_cache_write": plan_usage["cache_write"],
                "planner_cache_read": plan_usage["cache_read"],
                "planner_output": plan_usage["output"],
                "planner_usd_est": plan_usage["usd"],
            }
        executor = _executor_usage(wt, stage)
        plan_min = round(plan_min, 2)
        build_min = round(build_min, 2)
        verify_min = round(verify_min, 2)
        stage_min = round(plan_min + build_min + verify_min, 2)
        cum_usd = state["cum_usd"] + calls_usd
        cum_min = round(state["cum_min"] + stage_min, 2)
        row = {
            "task": task, "arm": label, "rep": rep, "stage": stage,
            "stage_usd": calls_usd, "cum_usd": cum_usd, **usage,
            **extras, **executor, "plan_min": plan_min, "build_min": build_min,
            "verify_min": verify_min, "stage_min": stage_min, "cum_min": cum_min,
            **scores, "note": note,
        }
        csv_path = bench.BENCH / "runs" / "stages.csv"
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        if not csv_path.exists():
            csv_path.write_text(",".join(COLUMNS) + "\n", encoding="utf-8")
        with csv_path.open("a", encoding="utf-8") as output:
            output.write(csv_line(row) + "\n")
        print(json.dumps(row))
        if build_broken:
            break
        state = {"sid": sid, "next_stage": stage + 1, "cum_usd": cum_usd, "cum_min": cum_min}
        _write_state(state_path, sid, stage + 1, cum_usd, cum_min)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("task")
    parser.add_argument("arm", choices=("PURE", "J", "J0", "K"))
    parser.add_argument("--rep", type=int, default=1)
    parser.add_argument("--continue", dest="continue_run", action="store_true")
    parser.add_argument("--stages", type=int)
    args = parser.parse_args()
    run(args.task, args.arm, args.rep, args.continue_run, args.stages)


if __name__ == "__main__":
    main()
