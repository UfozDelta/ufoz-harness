"""Tests for the opencode executor's stream handling (no server, no network)."""
import io
import sys
import threading
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".harness"))
from runner.executors import opencode  # noqa: E402
from runner.executors.opencode import OpenCodeExecutor  # noqa: E402
from runner.procs import EXIT_TIMEOUT  # noqa: E402


class _StubReader:
    def is_alive(self):
        return True

    def join(self, timeout=None):
        pass


@pytest.fixture
def quiet_executor(monkeypatch):
    """An executor wired to a stub server that accepts the prompt and then says nothing."""
    monkeypatch.setenv("HARNESS_OPENCODE_IDLE_S", "0.1")
    monkeypatch.setattr(opencode, "_http",
                        lambda url, path, body=None, timeout=600: {"id": "s1"})
    ex = OpenCodeExecutor(model="test/model")
    ex.url = "http://127.0.0.1:1"
    ex._reader = _StubReader()
    ex._connected = threading.Event()
    ex._connected.set()
    ex._events = []
    return ex


def test_idle_watchdog_aborts_a_silent_session(quiet_executor):
    t0 = time.monotonic()
    code, _usage, session, answered = quiet_executor._stream("hi", io.StringIO(), 60, None)
    elapsed = time.monotonic() - t0
    assert code == EXIT_TIMEOUT
    assert session == "s1"
    assert answered is False
    assert elapsed < 30, elapsed


def test_saw_event_is_set_for_matching_events(quiet_executor):
    quiet_executor._events.append(
        {"type": "session.idle", "properties": {"sessionID": "other"}})
    assert quiet_executor._drain(quiet_executor._events, "s1", io.StringIO(),
                                 quiet_executor._usage(), {"non_assistant": set(),
                                                          "logged": set()})["saw_event"] is False
    quiet_executor._events.append(
        {"type": "message.part.updated",
         "properties": {"sessionID": "s1", "part": {"type": "text", "text": "hi",
                                                    "messageID": "m1"}}})
    assert quiet_executor._drain(quiet_executor._events, "s1", io.StringIO(),
                                 quiet_executor._usage(), {"non_assistant": set(),
                                                          "logged": set()})["saw_event"] is True