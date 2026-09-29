"""Builds the Next.js app once, starts `next start` on a free port with a temp SHOP_DB_PATH,
and hands tests a base URL. Stack-agnostic: every test talks HTTP only."""
import json
import re
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

WIN = sys.platform == "win32"


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _kill(p):
    if WIN:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    else:
        p.kill()


@pytest.fixture(scope="session")
def db_path():
    d = Path(tempfile.mkdtemp(prefix="shop-hidden-"))
    yield d / "sub" / "shop.db"  # parent folder does not exist yet on purpose
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(scope="session")
def base(db_path):
    env = dict(os.environ, SHOP_DB_PATH=str(db_path), NEXT_TELEMETRY_DISABLED="1")
    b = subprocess.run("npm run build", shell=True, capture_output=True, text=True, env=env, timeout=900)
    if b.returncode != 0:
        pytest.exit(f"next build failed:\n{(b.stdout + b.stderr)[-3000:]}", returncode=1)
    port = _free_port()
    p = subprocess.Popen(f"npx next start -p {port}", shell=True, env=env,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(90):
        try:
            urllib.request.urlopen(url + "/", timeout=2)
            break
        except urllib.error.HTTPError:
            break  # server is up, the route just answered with an error
        except OSError:
            time.sleep(1)
    else:
        _kill(p)
        pytest.exit("next start never came up", returncode=1)
    yield url
    _kill(p)


def call(base, method, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            text = r.read().decode()
            status = r.status
    except urllib.error.HTTPError as e:
        text, status = e.read().decode(), e.code
    try:
        return status, json.loads(text)
    except ValueError:
        # HTML: drop React's text-node separators (`$<!-- -->29.99`) and unescape the streamed RSC payload,
        # where Next 16 puts notFound() UI (`\"data-testid\":\"not-found\"`), so markup checks see what renders
        text = text.replace("<!-- -->", "")
        streamed = re.findall(r'\\"data-testid\\":\\"([^\\"]+)\\"', text)
        missing = [t for t in streamed if f'data-testid="{t}"' not in text]
        text += "".join(f'<i data-testid="{t}"></i>' for t in missing)
        return status, text
