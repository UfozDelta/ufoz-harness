import json
import socket
import sys
import threading
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner.executors.llama import LlamaExecutor  # noqa: E402


class _Server:
    """A stand-in for llama-server in router mode: /models, /models/load, /health."""

    def __init__(self, models, health=200, load_ok=True):
        self.models = list(models)  # list of dicts, mutated by /models/load
        self.health = health
        self.load_ok = load_ok
        self.loaded = []
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
                if self.path == "/health":
                    self._send(outer.health)
                elif self.path == "/models":
                    self._send(200, json.dumps({"data": outer.models}).encode("utf-8"))
                else:
                    self._send(404, b"{}")

            def do_POST(self):
                if self.path != "/models/load":
                    self._send(404, b"{}")
                    return
                if not outer.load_ok:
                    self._send(500, b"{}")
                    return
                length = int(self.headers.get("Content-Length") or 0)
                wanted = json.loads(self.rfile.read(length) or b"{}").get("model")
                outer.loaded.append(wanted)
                for entry in outer.models:
                    if entry.get("id") == wanted:
                        entry["status"] = "loaded"
                self._send(200, b"{}")

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
    executor = LlamaExecutor(model)
    executor.url = server.url
    return executor


def _models_json(executor):
    return json.loads((Path(executor.env["PI_CODING_AGENT_DIR"]) / "models.json").read_text(encoding="utf-8"))


def test_start_writes_provider_and_loads_unloaded_model(monkeypatch):
    monkeypatch.delenv("HARNESS_LLAMA_MODEL", raising=False)
    with _Server([{"id": "qwen3", "status": "not-loaded", "meta": {"n_ctx": 4096}}]) as server:
        executor = _executor(server)
        executor.start()
        try:
            assert executor.model == "llamacpp/qwen3"
            assert server.loaded == ["qwen3"]
            config = _models_json(executor)["providers"]["llamacpp"]
            assert config["baseUrl"] == f"{server.url}/v1"
            assert config["api"] == "openai-completions"
            model = config["models"][0]
            assert model["id"] == "qwen3"
            assert model["contextWindow"] == 4096
            assert model["maxTokens"] == 2048
            assert model["reasoning"] is False
        finally:
            executor.stop()


def test_start_does_not_load_an_already_loaded_model(monkeypatch):
    monkeypatch.delenv("HARNESS_LLAMA_MODEL", raising=False)
    with _Server([{"id": "qwen3", "status": "loaded"}]) as server:
        executor = _executor(server)
        executor.start()
        try:
            assert server.loaded == []
            assert _models_json(executor)["providers"]["llamacpp"]["models"][0]["contextWindow"] == 32768
        finally:
            executor.stop()


def test_explicit_model_is_used_over_the_served_one(monkeypatch):
    monkeypatch.setenv("HARNESS_LLAMA_MODEL", "from-env")
    with _Server([{"id": "a", "status": "loaded"}, {"id": "b", "status": "loaded"}]) as server:
        executor = _executor(server, model="b")
        executor.start()
        try:
            assert executor.model == "llamacpp/b"
        finally:
            executor.stop()


def test_ambiguous_models_exit_listing_ids(monkeypatch):
    monkeypatch.delenv("HARNESS_LLAMA_MODEL", raising=False)
    with _Server([{"id": "a", "status": "loaded"}, {"id": "b", "status": "loaded"}]) as server:
        with pytest.raises(SystemExit) as e:
            _executor(server).start()
        assert "a" in str(e.value) and "b" in str(e.value)


def test_no_models_exit(monkeypatch):
    monkeypatch.delenv("HARNESS_LLAMA_MODEL", raising=False)
    with _Server([]) as server:
        with pytest.raises(SystemExit):
            _executor(server).start()


def test_dead_url_exits_with_the_start_command(monkeypatch):
    monkeypatch.delenv("HARNESS_LLAMA_MODEL", raising=False)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
    executor = LlamaExecutor()
    executor.url = f"http://127.0.0.1:{dead_port}"
    with pytest.raises(SystemExit) as e:
        executor.start()
    message = str(e.value)
    assert executor.url in message
    assert "llama-server --models-dir" in message


def test_probe_true_and_false(monkeypatch):
    with _Server([{"id": "qwen3", "status": "loaded"}], health=200) as server:
        assert _executor(server).probe() is True
    with _Server([{"id": "qwen3", "status": "loaded"}], health=503) as server:
        assert _executor(server).probe() is False
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        dead_port = sock.getsockname()[1]
    dead = LlamaExecutor()
    dead.url = f"http://127.0.0.1:{dead_port}"
    assert dead.probe() is False


def test_stop_removes_the_agent_dir(monkeypatch):
    monkeypatch.delenv("HARNESS_LLAMA_MODEL", raising=False)
    with _Server([{"id": "qwen3", "status": "loaded"}]) as server:
        executor = _executor(server)
        executor.start()
        agent_dir = Path(executor.env["PI_CODING_AGENT_DIR"])
        assert agent_dir.is_dir()
        executor.stop()
        assert not agent_dir.exists()
        assert executor.env is None


def test_run_forwards_env_to_run_pi(monkeypatch):
    monkeypatch.delenv("HARNESS_LLAMA_MODEL", raising=False)
    seen = {}

    def fake_run_pi(brief, log, timeout, feedback=None, session=None, raw_prompt=None, rules=None,
                    model=None, env=None):
        seen.update(model=model, env=env)
        return 0, {"input": 1}, "sid"

    # LlamaExecutor inherits PiExecutor.run, which calls run_pi in the pi module's namespace
    monkeypatch.setattr("runner.executors.pi.run_pi", fake_run_pi)
    with _Server([{"id": "qwen3", "status": "loaded"}]) as server:
        executor = _executor(server)
        executor.start()
        try:
            result = executor.run("brief.md", "log.txt", 60)
        finally:
            executor.stop()
    assert result.session == "sid"
    assert seen["model"] == "llamacpp/qwen3"
    assert "PI_CODING_AGENT_DIR" in seen["env"]
