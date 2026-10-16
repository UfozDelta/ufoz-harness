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

## Red-first default and bare `expect`

The runner proofs a task red-first: its acceptance must fail on the untouched
tree. Red-first is now on by default for a task whose acceptance calls a
`checks/` script; set `"red_first": false` to opt out (e.g. acceptance that
cannot fail before the work). A bare `expect` substring with no `checks/` script
in the acceptance and no `checks/` dir in the plan now lints as
`WARN <id>: loose expect`. A WARN never fails lint, but it flags a check that
matches any output — prefer a `checks/` script.
