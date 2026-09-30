"""Acceptance runs and compiler/test error extraction."""
import contextlib
import os
import re
import subprocess

from .procs import stop_process_tree


def parse_errors(text):
    """Return de-duplicated compiler/test errors as `path:line: message`."""
    errors = []
    lines = text.splitlines()
    ts_error = re.compile(r"^(?P<path>[^\r\n(]+)\((?P<line>\d+),\d+\): error TS\d+: (?P<msg>.*)$")
    generic_error = re.compile(r"^(?P<path>.+?):(?P<line>\d+):(?:\d+:)? (?P<msg>.*)$")
    python_error = re.compile(r'^File "(?P<path>[^"]+)", line (?P<line>\d+)$')
    for i, text_line in enumerate(lines):
        match = ts_error.match(text_line) or generic_error.match(text_line)
        if match:
            item = f"{match.group('path')}:{match.group('line')}: {match.group('msg').strip()}"
        else:
            match = python_error.match(text_line.strip())
            if not match:
                continue
            msg = next((line.strip() for line in lines[i + 1:] if line.strip()), "")
            item = f"{match.group('path')}:{match.group('line')}: {msg}"
        if item not in errors:
            errors.append(item)
    return errors


def run_acceptance(cmd, expect, timeout=300):
    # scripts run from a plan dir get that dir on sys.path, not the project root
    env = dict(os.environ, PYTHONPATH=os.pathsep.join(filter(None, [os.getcwd(), os.environ.get("PYTHONPATH")])))
    # utf-8 + replace: the Windows default codepage (cp1252) cannot decode tool output
    # such as vitest's check marks, which left stdout None and crashed the run
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL, env=env)
    try:
        stdout, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        # a grandchild inheriting the pipe keeps communicate() blocked long after the
        # shell itself is gone: kill the tree and stop waiting for the output
        stop_process_tree(proc)
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.communicate(timeout=5)
        return False, "acceptance command timed out"
    out = stdout or ""
    return proc.returncode == 0 and (expect is None or expect in out), out[-2000:]
