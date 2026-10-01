"""Validate the harness-suite fixtures: seed must be RED under hidden tests, solution GREEN.

Usage:
    python bench/suite/check_fixtures.py            # all sizes that exist
    python bench/suite/check_fixtures.py --size small
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

SUITE = Path(__file__).resolve().parent
FIXTURES = SUITE / "fixtures"
SIZES = ["small", "medium", "large"]
TMP_ROOT = SUITE / ".check-tmp"
CMD_TIMEOUT = 600

EXIT_INFRA = 2
EXIT_FAIL = 1
# subprocess exit codes that mean "the tool never ran", not "the tests failed"
INFRA_CODES = {127, 124}


class InfraError(RuntimeError):
    """A tool was missing/hung: the run says nothing about seed or solution."""


def node_tool(name: str) -> str:
    """Resolve a node CLI (npx, tsc, ...) so Windows finds npx.cmd."""
    found = shutil.which(name)
    if found is None:
        raise InfraError(f"required node tool not on PATH: {name}")
    return found


def copy_into(src: Path, dst: Path) -> None:
    """Copy the contents of src into dst, merging with whatever is already there."""
    dst.mkdir(parents=True, exist_ok=True)
    for entry in sorted(src.iterdir()):
        target = dst / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            shutil.copy2(entry, target)


def make_work(size: str) -> Path:
    seed = FIXTURES / size / "seed"
    if not seed.is_dir():
        raise InfraError(f"missing seed dir for size {size}: {seed}")
    hidden = FIXTURES / size / "hidden_tests"
    if not hidden.is_dir():
        raise InfraError(f"missing hidden_tests dir for size {size}: {hidden}")
    work = TMP_ROOT / f"{size}-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True)
    copy_into(seed, work)
    copy_into(FIXTURES / size / "hidden_tests", work)
    return work


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=CMD_TIMEOUT,
        )
    except FileNotFoundError:
        return 127, f"command not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {CMD_TIMEOUT}s: {' '.join(cmd)}"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def checks_for(size: str, work: Path) -> list[tuple[str, list[str]]]:
    """The (label, command) pairs that make up the test run for a work dir."""
    checks: list[tuple[str, list[str]]] = []
    py = sorted(p for p in work.rglob("*.py"))
    if py:
        checks.append(("pytest", [sys.executable, "-m", "pytest", "-q",
                                 "-p", "no:cacheprovider", "--rootdir", str(work)]))
    node = [p for p in work.rglob("*.ts")] + [p for p in work.rglob("*.tsx")]
    if node:
        npx = node_tool("npx")
        checks.append(("vitest", [npx, "--no-install", "vitest", "run"]))
        if (work / "tsconfig.json").is_file():
            checks.append(("tsc", [npx, "--no-install", "tsc", "--noEmit"]))
    if not checks:
        raise InfraError(f"no runnable tests found for size {size} in {work}")
    return checks


def run_all(checks: list[tuple[str, list[str]]], work: Path) -> dict[str, int]:
    results: dict[str, int] = {}
    for label, cmd in checks:
        code, out = run(cmd, work)
        results[label] = code
        print(f"    {label}: exit {code}")
        if code in INFRA_CODES:
            detail = out.strip().splitlines()[-1] if out.strip() else "no output"
            raise InfraError(f"{label} did not run (exit {code}): {detail}")
        if code != 0:
            for line in out.strip().splitlines()[-8:]:
                print(f"      | {line}")
    return results


def check_size(size: str) -> bool:
    print(f"[{size}] preparing work dir")
    work = make_work(size)
    try:
        checks = checks_for(size, work)
        print(f"[{size}] RED check (seed + hidden_tests)")
        red = run_all(checks, work)
        if all(code == 0 for code in red.values()):
            print(f"FAIL: {size} seed is not RED - hidden tests already pass on the seed")
            return False
        print(f"RED OK: {size}")

        print(f"[{size}] GREEN check (seed + solution + hidden_tests)")
        copy_into(FIXTURES / size / "solution", work)
        green = run_all(checks, work)
        if any(code != 0 for code in green.values()):
            bad = ", ".join(label for label, code in green.items() if code != 0)
            print(f"FAIL: {size} solution is not GREEN - failing: {bad}")
            return False
        print(f"GREEN OK: {size}")
        return True
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--size", choices=SIZES,
                        help="only check this size (default: every size that exists)")
    args = parser.parse_args(argv)

    if args.size:
        sizes = [args.size]
    else:
        sizes = [s for s in SIZES
                 if (FIXTURES / s / "seed").is_dir() and (FIXTURES / s / "hidden_tests").is_dir()]
    if not sizes:
        print("no fixtures found under bench/suite/fixtures")
        return 1

    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    try:
        for size in sizes:
            print(f"=== size: {size} ===")
            try:
                ok = check_size(size)
            except InfraError as exc:
                print(f"INFRA: {size}: {exc}")
                print("no verdict on this size - fix the environment and rerun")
                return EXIT_INFRA
            if not ok:
                failures.append(size)
    finally:
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    if failures:
        print(f"FAILED sizes: {', '.join(failures)}")
        return EXIT_FAIL
    print(f"OK: {', '.join(sizes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
