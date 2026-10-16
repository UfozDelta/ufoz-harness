import json
import socket
import sys
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner.executors.ollama import OllamaExecutor  # noqa: E402


class _Server:
    """A stand-in for an Ollama server: /api/tags lists the models, there is no load step."""

    def __init__(self, models, tags=200):
        self.models = list(models)  # list of dicts
        self.tags = tags
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            self.port = sock.getsockname()[1]
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _send(self, code, body=b""):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def do_GET(self):
                if self.path == "/api/tags":
                    self._send(outer.tags, json.dumps({"models": outer.models}).encode("utf-8"))
                else:
                    self._send(404, b"{}")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self):
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(5)


def _executor(server, model=None):
    executor = OllamaExecutor(model)
    executor.url = server.url
    return executor


def _models_json(executor):
    return json.loads((Path(executor.env["PI_CODING_AGENT_DIR"]) / "models.json").read_text(encoding="utf-8"))


def test_start_writes_provider_for_the_only_served_model(monkeypatch):
    monkeypatch.delenv("HARNESS_OLLAMA_MODEL", raising=False)
    with _Server([{"name": "qwen3", "model": "qwen3"}]) as server:
        executor = _executor(server)
        executor.start()
        try:
            assert executor.model == "ollama/qwen3"
            config = _models_json(executor)["providers"]["ollama"]
            assert config["baseUrl"] == f"{server.url}/v1"
            assert config["api"] == "openai-completions"
            model = config["models"][0]
            assert model["id"] == "qwen3"
            assert model["contextWindow"] == 32768
            assert model["maxTokens"] == 8192
            assert model["reasoning"] is False
        finally:
            executor.stop()


def test_explicit_model_is_used_over_the_served_one(monkeypatch):
    monkeypatch.setenv("HARNESS_OLLAMA_MODEL", "from-env")
    with _Server([{"name": "a", "model": "a"}, {"name": "b", "model": "b"}]) as server:
        executor = _executor(server, model="b")
        executor.start()
        try:
            assert executor.model == "ollama/b"
        finally:
            executor.stop()


def test_ambiguous_models_exit_listing_ids(monkeypatch):
    monkeypatch.delenv("HARNESS_OLLAMA_MODEL", raising=False)
    with _Server([{"name": "a", "model": "a"}, {"name": "b", "model": "b"}]) as server:
        with pytest.raises(SystemExit) as e:
            _executor(server).start()
        assert "a" in str(e.value) and "b" in str(e.value)


def test_no_models_exit(monkeypatch):
    monkeypatch.delenv("HARNESS_OLLAMA_MODEL", raising=False)
    with _Server([]) as server:
        with pytest.raises(SystemExit):
            _executor(server).start()


def test_dead_url_exits_with_the_start_command(monkeypatch):
    monkeypatch.delenv("HARNESS_OLLAMA_MODEL", raising=False)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
    executor = OllamaExecutor()
    executor.url = f"http://127.0.0.1:{dead_port}"
    with pytest.raises(SystemExit) as e:
        executor.start()
    message = str(e.value)
    assert executor.url in message
    assert "ollama serve" in message


def test_probe_true_and_false(monkeypatch):
    with _Server([{"name": "qwen3", "model": "qwen3"}], tags=200) as server:
        assert _executor(server).probe() is True
    with _Server([{"name": "qwen3", "model": "qwen3"}], tags=503) as server:
        assert _executor(server).probe() is False
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
    dead = OllamaExecutor()
    dead.url = f"http://127.0.0.1:{dead_port}"
    assert dead.probe() is False


def test_stop_removes_the_agent_dir(monkeypatch):
    monkeypatch.delenv("HARNESS_OLLAMA_MODEL", raising=False)
    with _Server([{"name": "qwen3", "model": "qwen3"}]) as server:
        executor = _executor(server)
        executor.start()
        agent_dir = Path(executor.env["PI_CODING_AGENT_DIR"])
        assert agent_dir.is_dir()
        executor.stop()
        assert not agent_dir.exists()
        assert executor.env is None


def test_run_forwards_env_to_run_pi(monkeypatch):
    monkeypatch.delenv("HARNESS_OLLAMA_MODEL", raising=False)
    seen = {}

    def fake_run_pi(brief, log, timeout, feedback=None, session=None, raw_prompt=None, rules=None,
                    model=None, env=None):
        seen.update(model=model, env=env)
        return 0, {"input": 1}, "sid"

    # OllamaExecutor inherits PiExecutor.run, which calls run_pi in the pi module's namespace
    monkeypatch.setattr("runner.executors.pi.run_pi", fake_run_pi)
    with _Server([{"name": "qwen3", "model": "qwen3"}]) as server:
        executor = _executor(server)
        executor.start()
        try:
            result = executor.run("brief.md", "log.txt", 60)
        finally:
            executor.stop()
    assert result.session == "sid"
    assert seen["model"] == "ollama/qwen3"
    assert "PI_CODING_AGENT_DIR" in seen["env"]
