#!/usr/bin/env python3
"""Run coding tasks through opencode and pi and compare their results."""

import argparse
import csv
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[2]
TASKS_ROOT = ROOT / ".harness" / "bench" / "tasks"
DEFAULT_MODEL = "opencode/space-bunny-free"
DEFAULT_MODELS = {"opencode": DEFAULT_MODEL, "pi": DEFAULT_MODEL}
DEFAULT_THINKING = "medium"
DEFAULT_PI = Path.home() / ".pi" / "agent" / "bin" / "pi-launcher.js"
# The same free Bunny model is spelled differently per provider, so one --model id cannot
# serve every arm. `--model pi=x,opencode=y` maps per arm; a bare id still applies to all of them.
MODEL_SETS = {
    "space-bunny-alpha": {
        "pi": "openrouter/stealth/space-bunny-alpha",
        # opencode rejects both stealth spellings ("Unexpected server error"); its only
        # working free Bunny is its own. Documented, not silently equal.
        "opencode": "opencode/space-bunny-free",
    },
}


def parse_models(value):
    """`harness=id` pairs -> {harness: id}; a bare id -> None, meaning "same id for every arm"."""
    if not value:
        return None
    if "=" not in value:
        return None
    mapping = {}
    for pair in value.split(","):
        harness, _, model = pair.partition("=")
        harness, model = harness.strip(), model.strip()
        if not harness or not model:
            raise ValueError(f"bad --model pair {pair!r}; want harness=id")
        mapping[harness] = model
    return mapping


def model_for(harness, args):
    """The model this arm runs: --model (one id, or one per arm) else the arm's own default.

    With a per-arm map an unmapped arm falls back to its own default: never to the raw
    "pi=a,opencode=b" argument, which is not a model id.
    """
    mapping = getattr(args, "model_map", None)
    if mapping:
        return mapping.get(harness) or DEFAULT_MODELS.get(harness, DEFAULT_MODEL)
    return args.model or DEFAULT_MODELS.get(harness, DEFAULT_MODEL)


PROMPT_SUFFIX = "Work in the current directory. Python. Do not ask questions; finish the whole task."
CSV_FIELDS = [
    "ts", "task", "harness", "model", "rep", "wall_s", "exit", "timed_out",
    "tests_passed", "tests_total", "turns", "tool_calls", "input", "output",
    "cache_read", "reasoning",
]


def parse(harness, path):
    """Parse an opencode or pi JSONL event log."""
    if harness not in ("opencode", "pi"):
        raise ValueError("harness must be 'opencode' or 'pi'")

    result = dict.fromkeys(
        ("turns", "tool_calls", "input", "output", "cache_read", "reasoning"), 0
    )
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            event = json.loads(line)
            if harness == "opencode":
                if event.get("type") == "step_finish":
                    result["turns"] += 1
                    tokens = event.get("part", {}).get("tokens", {})
                    result["input"] += tokens.get("input", 0)
                    result["output"] += tokens.get("output", 0)
                    result["reasoning"] += tokens.get("reasoning", 0)
                    result["cache_read"] += tokens.get("cache", {}).get("read", 0)
                elif event.get("type") == "tool_use":
                    result["tool_calls"] += 1
            elif harness == "pi" and event.get("type") == "message_end":
                message = event.get("message", {})
                if message.get("role") != "assistant":
                    continue
                result["turns"] += 1
                usage = message.get("usage", {})
                result["input"] += usage.get("input", 0)
                result["output"] += usage.get("output", 0)
                result["reasoning"] += usage.get("reasoning", 0)
                result["cache_read"] += usage.get("cacheRead", 0)
                result["tool_calls"] += sum(
                    item.get("type") == "toolCall"
                    for item in message.get("content", [])
                    if isinstance(item, dict)
                )
    return {key: int(value) for key, value in result.items()}


def task_prompt(task_dir):
    spec = task_dir / "spec.md"
    plan = task_dir / "plan" / "plan.md"
    source = spec if spec.is_file() else plan
    if not source.is_file():
        raise FileNotFoundError(f"no spec.md or plan/plan.md in {task_dir}")
    return f"{source.read_text(encoding='utf-8')}\n\n{PROMPT_SUFFIX}"


def command_for(harness, prompt, args, run_dir, create_config=True):
    if harness == "opencode":
        executable = shutil.which("opencode")
        if not executable:
            raise FileNotFoundError("opencode was not found on PATH")
        executable_path = Path(executable)
        real_executable = executable_path.parent / "node_modules" / "opencode-ai" / "bin" / "opencode.exe"
        if real_executable.is_file():
            executable = str(real_executable)
        config_home = run_dir / "xdg"
        if create_config:
            config_home.mkdir(exist_ok=True)
        command = [
            executable, "run", "--pure", "--dir", str(run_dir / "work"),
            "-m", model_for(harness, args), "--variant", args.thinking, "--format", "json",
            "--auto", prompt,
        ]
        return command, {"XDG_CONFIG_HOME": str(config_home)}
    pi = args.pi or DEFAULT_PI
    if not pi.is_file():
        raise FileNotFoundError(f"pi was not found at {pi}")
    node = shutil.which("node")
    if not node:
        raise FileNotFoundError("node was not found on PATH")
    command = [
        node, str(pi), "-p", "--mode", "json", "--no-session", "--no-extensions",
        "--no-skills", "--no-context-files", "--no-prompt-templates",
    ]
    if args.pi_ext:
        command.extend(["-e", str(args.pi_ext.resolve())])
    command.extend(["--model", model_for(harness, args), "--thinking", args.thinking, prompt])
    return command, None


def display_command(harness, command):
    one_line = [" ".join(shlex.quote(part) for part in command[:-1]), command[-1]]
    return harness + " " + " ".join(one_line).replace("\r", " ").replace("\n", " ")


def test_result(work_dir, task_dir, timeout):
    tests_target = work_dir / "_hidden_tests"
    if tests_target.exists():
        shutil.rmtree(tests_target)
    shutil.copytree(task_dir / "hidden_tests", tests_target)
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "_hidden_tests", "-q"],
            cwd=work_dir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = completed.stdout
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
    passed = sum(int(value) for value in re.findall(r"(\d+) passed", output))
    failed = sum(int(value) for value in re.findall(r"(\d+) failed", output))
    errors = sum(int(value) for value in re.findall(r"(\d+) error", output))
    return passed, passed + failed + errors, output


def append_result(csv_path, values):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0
    with csv_path.open("a", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        if write_header:
            writer.writeheader()
        writer.writerow(values)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", default="small,medium,large")
    parser.add_argument("--harness", default="opencode,pi")
    parser.add_argument("--reps", type=int, default=1)
    parser.add_argument("--model", default=None,
                        help=f"model id for every arm (default: {DEFAULT_MODEL}); "
                             f"a set name ({', '.join(MODEL_SETS)}) or per-arm pairs harness=id[,harness=id]")
    parser.add_argument("--thinking", default=DEFAULT_THINKING)
    parser.add_argument("--timeout", type=float, default=1200)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--pi", type=Path)
    parser.add_argument("--pi-ext", type=Path)
    parser.add_argument("--csv", type=Path, default=ROOT / "bench" / "speed" / "results.csv")
    parser.add_argument("--dry", action="store_true")
    args = parser.parse_args(argv)

    if args.model in MODEL_SETS:
        args.model_map = MODEL_SETS[args.model]
        args.model = None  # the map answers for every arm
    else:
        try:
            args.model_map = parse_models(args.model)
        except ValueError as exc:
            parser.error(str(exc))
    for harness, model in (args.model_map or {}).items():
        if harness not in DEFAULT_MODELS:
            parser.error(f"--model names an unknown harness: {harness} "
                         f"(choose from {', '.join(sorted(DEFAULT_MODELS))})")

    tasks = [name.strip() for name in args.tasks.split(",") if name.strip()]
    harnesses = [name.strip() for name in args.harness.split(",") if name.strip()]
    unknown = set(harnesses) - {"opencode", "pi"}
    if unknown:
        parser.error("unknown harness: " + ", ".join(sorted(unknown)))
    if args.reps < 1:
        parser.error("--reps must be at least 1")

    for rep in range(args.reps):
        for task_index, task_name in enumerate(tasks):
            task_dir = TASKS_ROOT / task_name
            prompt = task_prompt(task_dir)
            order = list(harnesses)
            if (rep + task_index) % 2:
                order.reverse()
            for harness in order:
                if args.dry:
                    run_dir = Path("<out>") / task_name / harness / f"r{rep}"
                    command, _ = command_for(
                        harness, prompt, args, run_dir, create_config=False
                    )
                    print(display_command(harness, command))
                else:
                    run_one(task_name, task_dir, harness, rep, prompt, args)

    return 0


def run_one(task_name, task_dir, harness, rep, prompt, args):
    base = args.out or (Path(tempfile.gettempdir()) / "harness-speed-test-runs")
    run_dir = Path(base) / task_name / harness / f"r{rep}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    work_dir = run_dir / "work"
    work_dir.mkdir()
    seed = task_dir / "seed"
    if seed.is_dir():
        shutil.copytree(seed, work_dir, dirs_exist_ok=True)

    started = time.monotonic()
    timed_out = False
    command, extra_env = command_for(harness, prompt, args, run_dir)
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    env["PWD"] = str(work_dir)
    with (run_dir / "events.jsonl").open("w", encoding="utf-8") as events, \
            (run_dir / "stderr.txt").open("w", encoding="utf-8") as errors:
        try:
            completed = subprocess.run(
                command,
                cwd=work_dir,
                stdin=subprocess.DEVNULL,
                stdout=events,
                stderr=errors,
                env=env,
                timeout=args.timeout,
                check=False,
            )
            exit_code = completed.returncode
        except subprocess.TimeoutExpired:
            timed_out = True
            exit_code = 124
    wall = time.monotonic() - started
    stats = parse(harness, run_dir / "events.jsonl")
    passed, total, test_output = test_result(work_dir, task_dir, args.timeout)
    (run_dir / "pytest.txt").write_text(test_output, encoding="utf-8")
    append_result(args.csv, {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task": task_name,
        "harness": harness,
        "model": model_for(harness, args),
        "rep": rep,
        "wall_s": f"{wall:.3f}",
        "exit": exit_code,
        "timed_out": int(timed_out),
        "tests_passed": passed,
        "tests_total": total,
        **stats,
    })
    print(f"{task_name} {harness} r{rep} wall_s={wall:.3f} tests={passed}/{total}")


if __name__ == "__main__":
    raise SystemExit(main())
