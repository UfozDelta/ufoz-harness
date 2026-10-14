"""Executors: who writes the code. The run loop asks for one by name and never imports
a backend module directly."""
from .base import ExecResult, Executor
from .claude import ClaudeExecutor
from .llama import LlamaExecutor
from .opencode import OpenCodeExecutor
from .pi import PiExecutor

REGISTRY = {"pi": PiExecutor, "claude": ClaudeExecutor,
            "opencode": OpenCodeExecutor, "llama": LlamaExecutor}


def get(name, **opts) -> Executor:
    """Build the executor named on the command line (--executor)."""
    try:
        cls = REGISTRY[name]
    except KeyError:
        raise SystemExit(f"unknown executor: {name} (choose from {', '.join(sorted(REGISTRY))})")
    return cls(**opts)
