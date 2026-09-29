import argparse
import ast
import hashlib
import os
from pathlib import Path
import re
import sys


SKIP_DIRS = {
    ".git",
    "node_modules",
    ".next",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".harness",
    ".claude",
    ".opencode",
    ".pytest_cache",
    "coverage",
}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml"}
JS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs"}
ROUTE_SUFFIXES = {".ts", ".tsx", ".js", ".jsx"}
EXPORT_RE = re.compile(
    r"^export\s+(?:default\s+)?(?:async\s+)?(?:function\*?|const|let|class|interface|type|enum)\s+([A-Za-z_$][\w$]*)",
    re.MULTILINE,
)
BARE_DEFAULT_RE = re.compile(r"^export\s+(default)\s*$", re.MULTILINE)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--out")
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def is_skipped_file(path):
    return (
        path.name in SKIP_FILES
        or path.suffix == ".pyc"
        or path.suffix == ".map"
        or path.stat().st_size > 200 * 1024
    )


def included_files(root):
    files = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        relative_directory = Path(directory).relative_to(root)
        for filename in sorted(filenames):
            path = Path(directory) / filename
            if any(part in SKIP_DIRS for part in relative_directory.parts):
                continue
            if is_skipped_file(path):
                continue
            relative_path = path.relative_to(root).as_posix()
            files.append((relative_path, path))
    return sorted(files, key=lambda item: item[0])


def fingerprint(files):
    result = hashlib.sha1()
    for relative_path, path in files:
        file_hash = hashlib.sha1(path.read_bytes()).hexdigest()
        result.update((relative_path + "\0" + file_hash).encode("utf-8"))
    return result.hexdigest()[:12]


def python_symbols(path):
    try:
        tree = ast.parse(path.read_bytes())
    except SyntaxError:
        return []
    return [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and not node.name.startswith("_")
    ]


def js_symbols(path):
    source = path.read_text(encoding="utf-8", errors="replace")
    symbols = EXPORT_RE.findall(source)
    symbols.extend(BARE_DEFAULT_RE.findall(source))
    return symbols


def symbols_for(path):
    if path.suffix == ".py":
        return python_symbols(path)
    if path.suffix in JS_SUFFIXES:
        return js_symbols(path)
    return []


def route_for(relative_path):
    parts = Path(relative_path).parts
    try:
        app_index = parts.index("app")
    except ValueError:
        return None
    suffix = Path(relative_path).suffix
    if suffix not in ROUTE_SUFFIXES or not (
        Path(relative_path).name.startswith("page.") or Path(relative_path).name.startswith("route.")
    ):
        return None
    route_parts = [part for part in parts[app_index + 1 : -1] if not (part.startswith("(") and part.endswith(")"))]
    return "/" + "/".join(route_parts)


def preserved_notes(out_path):
    if not out_path.exists():
        return "- (main session: add decisions/conventions here)\n"
    content = out_path.read_text(encoding="utf-8")
    marker = "## Notes\n"
    if marker in content:
        return content.split(marker, 1)[1]
    return "- (main session: add decisions/conventions here)\n"


def build_map(root, out_path, check):
    files = included_files(root)
    current_fingerprint = fingerprint(files)

    if check:
        if out_path.exists():
            existing = out_path.read_text(encoding="utf-8")
            match = re.search(r"^fingerprint: ([0-9a-f]{12})$", existing, re.MULTILINE)
            if match and match.group(1) == current_fingerprint:
                return 0
        print("stale")
        return 1

    notes = preserved_notes(out_path)
    lines = [
        "# Repo map",
        f"fingerprint: {current_fingerprint}",
        "Regenerate: `python .harness/build_map.py` (check: `--check`). Read this before exploring.",
        "",
        "## Routes",
    ]
    routes = []
    for relative_path, path in files:
        route = route_for(relative_path)
        if route is not None:
            routes.append((route, relative_path))
    lines.extend(f"- `{route}` -> {relative_path}" for route, relative_path in routes)
    if not routes:
        lines.append("- none")

    lines.extend(["", "## Files"])
    for relative_path, path in files:
        symbols = symbols_for(path)
        suffix = ""
        if symbols:
            suffix = f": {', '.join(symbols[:10])}"
            if len(symbols) > 10:
                suffix += ", ..."
        lines.append(f"- {relative_path}{suffix}")

    lines.extend(["", "## Notes"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n" + notes, encoding="utf-8")
    return 0


def main():
    args = parse_args()
    root = Path(args.root)
    out_path = Path(args.out) if args.out else root / ".harness/context/REPO_MAP.md"
    return build_map(root, out_path, args.check)


if __name__ == "__main__":
    sys.exit(main())
