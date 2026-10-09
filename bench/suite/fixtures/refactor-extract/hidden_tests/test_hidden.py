import ast
import importlib
from pathlib import Path

import pytest

import report

ROOT = Path(__file__).resolve().parent

MIXED = (
    "2024-05-01 INFO started job 120ms\n"
    "2024-05-01 ERROR disk full 300ms\n"
    "garbage\n"
    "2024-05-02 INFO finished job 45ms\n"
    "2024-05-03 WARN slow query 210ms\n"
)

SINGLE = "2024-01-10 DEBUG cache miss 7ms\n"

EMPTY = ""

GOLDEN_MIXED = (
    "records: 4\n"
    "first: 2024-05-01\n"
    "last: 2024-05-03\n"
    "total_ms: 675\n"
    "max_ms: 300\n"
    "slowest: disk full\n"
    "levels:\n"
    "  ERROR: 1\n"
    "  INFO: 2\n"
    "  WARN: 1\n"
)

GOLDEN_SINGLE = (
    "records: 1\n"
    "first: 2024-01-10\n"
    "last: 2024-01-10\n"
    "total_ms: 7\n"
    "max_ms: 7\n"
    "slowest: cache miss\n"
    "levels:\n"
    "  DEBUG: 1\n"
)

GOLDEN_EMPTY = (
    "records: 0\n"
    "first: -\n"
    "last: -\n"
    "total_ms: 0\n"
    "max_ms: 0\n"
    "slowest: -\n"
    "levels:\n"
)


@pytest.mark.parametrize("text, golden", [
    (MIXED, GOLDEN_MIXED),
    (SINGLE, GOLDEN_SINGLE),
    (EMPTY, GOLDEN_EMPTY),
])
def test_build_golden_output(text, golden):
    assert report.build(text) == golden


@pytest.mark.parametrize("name, module", [
    ("parse_lines", "report.parse"),
    ("summarize", "report.summarize"),
    ("render", "report.render"),
])
def test_function_lives_in_its_own_module(name, module):
    assert getattr(report, name).__module__ == module


@pytest.mark.parametrize("module", ["report.parse", "report.summarize", "report.render"])
def test_submodule_importable(module):
    assert importlib.import_module(module) is not None


def test_parse_module_does_not_import_render():
    source = (ROOT / "report" / "parse.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
            imported.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
    assert not any("render" in name for name in imported), imported


def test_build_equals_composition():
    assert report.build(MIXED) == report.render(report.summarize(report.parse_lines(MIXED)))


def test_package_init_is_small():
    source = (ROOT / "report" / "__init__.py").read_text(encoding="utf-8")
    non_blank = [line for line in source.splitlines() if line.strip()]
    assert len(non_blank) <= 15
