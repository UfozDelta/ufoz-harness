"""Validate the harness-suite fixtures: seed must be RED under hidden tests, solution GREEN.

Usage:
    python bench/suite/check_fixtures.py            # every task dir with seed/ and hidden_tests/
    python bench/suite/check_fixtures.py --size small
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

SUITE = Path(__file__).resolve().parent
FIXTURES = SUITE / "fixtures"
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


def make_work(size: str, extra: tuple[str, ...] = ("hidden_tests",)) -> Path:
    seed = FIXTURES / size / "seed"
    if not seed.is_dir():
        raise InfraError(f"missing seed dir for size {size}: {seed}")
    for name in extra:
        layer = FIXTURES / size / name
        if not layer.is_dir():
            raise InfraError(f"missing {name} dir for size {size}: {layer}")
    work = TMP_ROOT / f"{size}-{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True)
    copy_into(seed, work)
    for name in extra:
        copy_into(FIXTURES / size / name, work)
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


def seed_checks_for(work: Path) -> list[tuple[str, list[str]]]:
    """Only the seed's own tests: pytest if it has test_*.py, vitest if it has *.test.ts(x)."""
    checks: list[tuple[str, list[str]]] = []
    if any(work.rglob("test_*.py")):
        checks.append(("pytest", [sys.executable, "-m", "pytest", "-q",
                                 "-p", "no:cacheprovider", "--rootdir", str(work)]))
    if any(work.rglob("*.test.ts")) or any(work.rglob("*.test.tsx")):
        checks.append(("vitest", [node_tool("npx"), "--no-install", "vitest", "run"]))
    return checks


PACKAGE_DIRS = {"medium": "seed", "large": "seed/web"}


def check_package(size: str) -> bool:
    rel = PACKAGE_DIRS.get(size)
    if rel is None:
        return True
    pkg_dir = FIXTURES / size / rel
    try:
        pkg = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((pkg_dir / "package-lock.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"FAIL: {size} package files unreadable in {pkg_dir}: {exc}")
        return False
    if lock.get("packages", {}).get("", {}).get("devDependencies") != pkg.get("devDependencies"):
        print(f"FAIL: {size} package-lock.json devDependencies differ from package.json")
        return False
    return True


def _seed_checks_pass(size: str, extra: tuple[str, ...]) -> bool:
    work = make_work(size, extra)
    try:
        return all(code == 0 for code in run_all(seed_checks_for(work), work).values())
    finally:
        shutil.rmtree(work, ignore_errors=True)


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


def runs_agree(results: list[dict[str, int]]) -> bool:
    """True iff every run has the same {label: passed} map as the first run."""
    if not results:
        return True
    first = {label: code == 0 for label, code in results[0].items()}
    return all({label: code == 0 for label, code in run_.items()} == first for run_ in results[1:])


def check_size(size: str, repeat: int = 5) -> bool:
    if not check_package(size):
        return False

    print(f"[{size}] SEED check (seed alone)")
    if not _seed_checks_pass(size, ()):
        print(f"FAIL: {size} seed's own tests are not green on the seed")
        return False

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
        runs = [green]
        for _ in range(repeat - 1):
            runs.append(run_all(checks, work))
        if not runs_agree(runs):
            print(f"FAIL: {size} flaky - repeated GREEN runs disagree: {runs}")
            return False
        print(f"GREEN OK: {size} (x{repeat} runs agree)")

        print(f"[{size}] SOLUTION check (seed + solution, no hidden_tests)")
        if not _seed_checks_pass(size, ("solution",)):
            print(f"FAIL: {size} seed+solution tests are not green without hidden_tests")
            return False
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
    parser.add_argument("--size",
                        help="only check this task id (default: every task that has seed/ and hidden_tests/)")
    parser.add_argument("--repeat", type=int, default=5,
                        help="GREEN runs per size that must agree (default 5, min 1)")
    args = parser.parse_args(argv)
    repeat = max(1, args.repeat)

    if args.size:
        if not (FIXTURES / args.size).is_dir():
            print(f"unknown task: {args.size}")
            return 1
        sizes = [args.size]
    else:
        sizes = [d.name for d in sorted(FIXTURES.iterdir())
                 if d.is_dir() and d.name[0] not in "_."
                 and (d / "seed").is_dir() and (d / "hidden_tests").is_dir()]
    if not sizes:
        print("no fixtures found under bench/suite/fixtures")
        return 1

    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    failures: list[str] = []
    try:
        for size in sizes:
            print(f"=== size: {size} ===")
            try:
                ok = check_size(size, repeat)
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
