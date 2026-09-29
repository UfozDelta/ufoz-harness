"""The llama executor: pi is the transport, a local llama.cpp `llama-server` in router mode is
the model. A user-started server (never spawned here) serves a GGUF over its OpenAI-compatible
API; pi talks to it through a custom provider written into a throwaway PI_CODING_AGENT_DIR, so
the global ~/.pi/agent config is never touched.
"""
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .pi import PiExecutor

DEFAULT_URL = "http://127.0.0.1:8080"
DEFAULT_CTX = 32768
MAX_TOKENS = 8192
LOAD_TIMEOUT = 300
READY_STATUSES = ("loaded", "sleeping")


def _http(url, path, body=None, timeout=30):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"} if data is not None else {}
    request = urllib.request.Request(f"{url}{path}", data=data, headers=headers,
                                     method="GET" if body is None else "POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _entries(payload):
    """`/models` answers a list, or an object wrapping it under data/models."""
    if isinstance(payload, list):
        return [m for m in payload if isinstance(m, dict)]
    if isinstance(payload, dict):
        for key in ("data", "models"):
            if isinstance(payload.get(key), list):
                return [m for m in payload[key] if isinstance(m, dict)]
    return []


def _model_id(entry):
    return entry.get("id") or entry.get("model") or ""


def _status(entry):
    """The router reports `status: {"value": "loaded", ...}`; older builds a plain string."""
    status = entry.get("status") or entry.get("state") or ""
    if isinstance(status, dict):
        status = status.get("value") or ""
    return str(status).lower()


def _context_window(entry):
    value = (entry.get("meta") or {}).get("n_ctx")
    return value if isinstance(value, int) and value > 0 else DEFAULT_CTX


class LlamaExecutor(PiExecutor):
    name = "llama"
    thread_safe = False  # one CPU/GPU slot: a plan may not run tasks in parallel

    def __init__(self, model=None):
        self.requested = model or os.environ.get("HARNESS_LLAMA_MODEL") or None
        self.model = self.requested
        self.url = os.environ.get("HARNESS_LLAMA_URL") or DEFAULT_URL
        self._config = None

    def start(self):
        """Point pi at the router: resolve the model, write a private models.json, and make
        the router load that model (router mode does not autoload --models-dir models)."""
        entries = self._list_models()
        wanted = self.requested
        if not wanted:
            ids = [_model_id(m) for m in entries if _model_id(m)]
            if len(ids) == 1:
                wanted = ids[0]
            else:
                sys.exit(f"llama: cannot pick a model on {self.url}: {len(ids)} served "
                         f"({', '.join(ids) or 'none'}). Pass --executor-model or set HARNESS_LLAMA_MODEL.")
        self._load(wanted, entries)
        self.model = f"llamacpp/{wanted}"
        self._config = tempfile.TemporaryDirectory(prefix="harness-llama-")
        agent_dir = Path(self._config.name)
        (agent_dir / "models.json").write_text(
            json.dumps(self._provider_config(wanted, entries), indent=2) + "\n", encoding="utf-8")
        self.env = {"PI_CODING_AGENT_DIR": str(agent_dir)}

    def stop(self):
        if self._config is not None:
            self._config.cleanup()
            self._config = None
        self.env = None

    def probe(self) -> bool:
        """The router answers /health with 200 while it is up; there are no remote rate limits."""
        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=10) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def _list_models(self):
        try:
            payload = _http(self.url, "/models", timeout=10)
        except (urllib.error.URLError, OSError, ValueError) as e:
            sys.exit(f"llama: no llama-server at {self.url} ({e}). Start one with:\n"
                     f"  llama-server --models-dir <dir with the GGUF> --jinja --port 8080")
        return _entries(payload)

    def _load(self, wanted, entries):
        entry = next((m for m in entries if _model_id(m) == wanted), None)
        if entry is not None and _status(entry) in READY_STATUSES:
            return
        try:
            _http(self.url, "/models/load", {"model": wanted}, timeout=60)
        except (urllib.error.URLError, OSError, ValueError) as e:
            sys.exit(f"llama: {self.url} refused to load model {wanted!r} ({e})")
        deadline = time.monotonic() + LOAD_TIMEOUT
        while True:
            entries = _entries(_http(self.url, "/models", timeout=10))
            entry = next((m for m in entries if _model_id(m) == wanted), None)
            if entry is not None and _status(entry) in READY_STATUSES:
                return
            if time.monotonic() > deadline:
                sys.exit(f"llama: model {wanted!r} was not loaded after {LOAD_TIMEOUT}s on {self.url}")
            time.sleep(0.5)

    def _provider_config(self, wanted, entries):
        entry = next((m for m in entries if _model_id(m) == wanted), {})
        ctx = _context_window(entry)
        return {"providers": {"llamacpp": {
            "baseUrl": f"{self.url}/v1",
            "api": "openai-completions",
            "apiKey": "local",
            "models": [{
                "id": wanted,
                "reasoning": False,
                "input": ["text"],
                "contextWindow": ctx,
                "maxTokens": min(MAX_TOKENS, ctx // 2),
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            }],
        }}}
