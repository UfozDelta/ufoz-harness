import re
import subprocess
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / ".harness" / "build_map.py"


def run_map(root, out, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--out", str(out), *args],
        capture_output=True,
        text=True,
    )


def test_python_symbols_and_syntax_error(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "service.py").write_text(
        "def public():\n    pass\n\n"
        "async def fetch():\n    pass\n\n"
        "class Service:\n    pass\n\n"
        "def _private():\n    pass\n",
        encoding="utf-8",
    )
    (root / "broken.py").write_text("def nope(:\n", encoding="utf-8")
    out = tmp_path / "map.md"

    result = run_map(root, out)

    assert result.returncode == 0
    text = out.read_text(encoding="utf-8")
    assert "- broken.py" in text
    assert "- service.py: public, fetch, Service" in text
    assert "_private" not in text


def test_typescript_and_javascript_export_symbols(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source = (
        "export default function Foo() {}\n"
        "export const bar = 1\n"
        "export default\n"
    )
    (root / "exports.ts").write_text(source, encoding="utf-8")
    (root / "component.jsx").write_text(
        "export class Button {}\nexport type Props = {}\n", encoding="utf-8"
    )
    out = tmp_path / "map.md"

    result = run_map(root, out)

    assert result.returncode == 0
    text = out.read_text(encoding="utf-8")
    assert "- exports.ts: Foo, bar, default" in text
    assert "- component.jsx: Button, Props" in text


def test_public_symbol_truncation(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    for count in (12, 11, 10):
        symbols = "\n".join(f"def s{index}(): pass" for index in range(1, count + 1))
        (root / f"symbols_{count}.py").write_text(symbols + "\n", encoding="utf-8")
    out = tmp_path / "map.md"

    result = run_map(root, out)

    assert result.returncode == 0
    text = out.read_text(encoding="utf-8")
    expected = ", ".join(f"s{index}" for index in range(1, 11))
    assert f"- symbols_12.py: {expected}, ..." in text
    assert f"- symbols_11.py: {expected}, ..." in text
    assert f"- symbols_10.py: {expected}\n" in text


def test_routes_and_skipped_paths(tmp_path):
    root = tmp_path / "repo"
    (root / "app").mkdir(parents=True)
    (root / "app" / "(shop)" / "cart").mkdir(parents=True)
    (root / "app" / "api" / "orders").mkdir(parents=True)
    (root / "app" / "page.tsx").write_text("export default function Page() {}\n", encoding="utf-8")
    (root / "app" / "(shop)" / "cart" / "page.tsx").write_text("export default function Cart() {}\n", encoding="utf-8")
    (root / "app" / "api" / "orders" / "route.ts").write_text("export function GET() {}\n", encoding="utf-8")
    (root / "package-lock.json").write_text("{}", encoding="utf-8")
    (root / "node_modules").mkdir()
    (root / "node_modules" / "ignored.js").write_text("export const ignored = true\n", encoding="utf-8")
    (root / ".next").mkdir()
    (root / ".next" / "ignored.ts").write_text("export const ignored = true\n", encoding="utf-8")
    out = tmp_path / "map.md"

    result = run_map(root, out)

    assert result.returncode == 0
    text = out.read_text(encoding="utf-8")
    assert "- `/` -> app/page.tsx" in text
    assert "- `/cart` -> app/(shop)/cart/page.tsx" in text
    assert "- `/api/orders` -> app/api/orders/route.ts" in text
    assert "package-lock.json" not in text
    assert "node_modules" not in text
    assert ".next" not in text


def test_check_status_and_writes_nothing(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    source = root / "source.txt"
    source.write_text("one\n", encoding="utf-8")
    out = tmp_path / "missing" / "map.md"

    missing = run_map(root, out, "--check")
    assert missing.returncode == 1
    assert "stale" in missing.stdout
    assert not out.exists()
    assert not out.parent.exists()

    built = run_map(root, out)
    assert built.returncode == 0
    current = run_map(root, out, "--check")
    assert current.returncode == 0
    before = out.read_bytes()

    source.write_text("two\n", encoding="utf-8")
    stale = run_map(root, out, "--check")
    assert stale.returncode == 1
    assert "stale" in stale.stdout
    assert out.read_bytes() == before


def test_notes_preserved_and_fingerprint_stable(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "source.txt").write_text("content\n", encoding="utf-8")
    out = tmp_path / "map.md"

    assert run_map(root, out).returncode == 0
    first = out.read_text(encoding="utf-8")
    fingerprint = re.search(r"^fingerprint: ([0-9a-f]{12})$", first, re.MULTILINE).group(1)
    first = first.split("## Notes\n", 1)[0] + "## Notes\n- keep this\n- unchanged\n"
    out.write_text(first, encoding="utf-8")

    assert run_map(root, out).returncode == 0
    rebuilt = out.read_text(encoding="utf-8")
    assert rebuilt.endswith("## Notes\n- keep this\n- unchanged\n")
    assert re.search(r"^fingerprint: ([0-9a-f]{12})$", rebuilt, re.MULTILINE).group(1) == fingerprint

    assert run_map(root, out).returncode == 0
    unchanged = out.read_text(encoding="utf-8")
    assert re.search(r"^fingerprint: ([0-9a-f]{12})$", unchanged, re.MULTILINE).group(1) == fingerprint


def test_repeated_rebuilds_are_byte_identical_with_custom_notes(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "source.txt").write_text("content\n", encoding="utf-8")
    out = tmp_path / "map.md"

    assert run_map(root, out).returncode == 0
    generated = out.read_text(encoding="utf-8")
    custom_notes = "## Notes\n- custom decision\n\n- another note\n"
    out.write_text(generated.split("## Notes\n", 1)[0] + custom_notes, encoding="utf-8")

    assert run_map(root, out).returncode == 0
    first_rebuild = out.read_bytes()
    assert run_map(root, out).returncode == 0
    second_rebuild = out.read_bytes()
    assert run_map(root, out).returncode == 0
    third_rebuild = out.read_bytes()

    assert first_rebuild == second_rebuild == third_rebuild
    assert out.read_text(encoding="utf-8").split("## Notes\n", 1)[1] == custom_notes.split("## Notes\n", 1)[1]
