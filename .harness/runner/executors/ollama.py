"""The ollama executor: pi is the transport, a user-started Ollama server is the model. Ollama
serves an OpenAI-compatible API; pi talks to it through a custom provider written into a throwaway
PI_CODING_AGENT_DIR, so the global ~/.pi/agent config is never touched. Unlike the llama executor
there is no router/load step: Ollama loads a model on first use.
"""
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .pi import PiExecutor

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_CTX = 32768
MAX_TOKENS = 8192
PROVIDER = "ollama"


def _http(url, path, timeout=30):
    request = urllib.request.Request(f"{url}{path}", method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read()
    return json.loads(raw) if raw else None


def _entries(payload):
    """`/api/tags` answers `{"models": [...]}`; a bare list is accepted too."""
    if isinstance(payload, dict) and isinstance(payload.get("models"), list):
        return [m for m in payload["models"] if isinstance(m, dict)]
    if isinstance(payload, list):
        return [m for m in payload if isinstance(m, dict)]
    return []


def _model_id(entry):
    return entry.get("model") or entry.get("name") or ""


class OllamaExecutor(PiExecutor):
    name = "ollama"
    thread_safe = False  # one local model instance: a plan may not run tasks in parallel

    def __init__(self, model=None):
        self.requested = model or os.environ.get("HARNESS_OLLAMA_MODEL") or None
        self.model = self.requested
        self.url = os.environ.get("HARNESS_OLLAMA_URL") or DEFAULT_URL
        self._config = None

    def start(self):
        """Point pi at Ollama: resolve the model against /api/tags, then write a private
        models.json. No load call: Ollama loads the model on the first request."""
        entries = self._list_models()
        wanted = self.requested
        if not wanted:
            ids = [_model_id(m) for m in entries if _model_id(m)]
            if len(ids) == 1:
                wanted = ids[0]
            else:
                sys.exit(f"ollama: cannot pick a model on {self.url}: {len(ids)} served "
                         f"({', '.join(ids) or 'none'}). Pass --executor ollama:<model> or "
                         f"set HARNESS_OLLAMA_MODEL.")
        self.model = f"{PROVIDER}/{wanted}"
        self._config = tempfile.TemporaryDirectory(prefix="harness-ollama-")
        agent_dir = Path(self._config.name)
        (agent_dir / "models.json").write_text(
            json.dumps(self._provider_config(wanted), indent=2) + "\n", encoding="utf-8")
        self.env = {"PI_CODING_AGENT_DIR": str(agent_dir)}

    def stop(self):
        if self._config is not None:
            self._config.cleanup()
            self._config = None
        self.env = None

    def probe(self) -> bool:
        """Ollama answers /api/tags with 200 while it is up; there are no remote rate limits."""
        try:
            with urllib.request.urlopen(f"{self.url}/api/tags", timeout=10) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError, ValueError):
            return False

    def _list_models(self):
        try:
            payload = _http(self.url, "/api/tags", timeout=10)
        except (urllib.error.URLError, OSError, ValueError) as e:
            sys.exit(f"ollama: no Ollama server at {self.url} ({e}). Start one with:\n"
                     f"  ollama serve   (then `ollama pull <model>`)")
        return _entries(payload)

    def _provider_config(self, wanted):
        return {"providers": {PROVIDER: {
            "baseUrl": f"{self.url}/v1",
            "api": "openai-completions",
            "apiKey": PROVIDER,
            "models": [{
                "id": wanted,
                "reasoning": False,
                "input": ["text"],
                "contextWindow": DEFAULT_CTX,
                "maxTokens": min(MAX_TOKENS, DEFAULT_CTX // 2),
                "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
            }],
        }}}
