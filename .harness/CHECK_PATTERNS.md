# Check patterns

Reusable acceptance-check shapes for `.harness/plans/<slug>/checks/check_t*.py`.

## Exactly-once side effect

Use when a task wires a side-effecting call (pixel/analytics fire, storage
write, event emit) that must happen from exactly one code path. Catches the
"wired from both the init snippet and an explicit call site" bug class
(seen in the large_lego benchmark: Meta PageView fired twice).

    import re
    from pathlib import Path

    src = Path("path/to/file.tsx").read_text(encoding="utf-8")
    calls = re.findall(r"fbq\(\s*['\"]track['\"]\s*,\s*['\"]PageView['\"]", src)
    assert len(calls) == 1, f"expected exactly 1 PageView call, found {len(calls)}"

Adapt the regex to the actual call (`gtag('event', ...)`, `ttq.track(...)`,
a logger call, a webhook POST). The key property: count occurrences across
ALL files the task touched, not just the one file expected to have it — the
duplicate is often in a second file (e.g. a snippet component AND a hook).
