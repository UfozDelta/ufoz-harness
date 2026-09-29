"""Process handling and usage constants shared by every executor."""
import os
import re
import subprocess

ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
TOKEN_KEYS = ("input", "output", "reasoning", "cache_read")
# executor exit codes, so the run loop can branch without magic numbers per executor
EXIT_RATE_LIMIT = 75
EXIT_TIMEOUT = 124


def zero_usage():
    return {**dict.fromkeys(TOKEN_KEYS, 0), "cost": 0.0}


def stop_process_tree(p):
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    else:
        p.kill()
