import re

import textkit

# The spec says only "handle unicode sensibly": keeping, transliterating or dropping non-ASCII
# letters are all fine. The invariant core is: lowercase, single hyphens between word characters,
# no leading/trailing hyphen, no whitespace or punctuation.
SLUG_RE = re.compile(r"^[^\W_]+(-[^\W_]+)*$")

SAMPLES = [
    "Hello, World!",
    "  spaced   out  ",
    "a\tb\n\nc",
    "--Leading and trailing--",
    "Café Münster",
    "Ünïcödé Tëxt",
    "C++ & Python 3.14!",
    "2024: the year",
    "already-a-slug",
    "!!!",
    "東京 tokyo",
    "Naïve façade",
    "x",
    "  ",
    "Mixed_CASE_words",
    "Ärger über Straßen",
]


def test_output_is_valid_slug_or_empty():
    for sample in SAMPLES:
        out = textkit.slugify(sample)
        assert out == "" or (SLUG_RE.match(out) and out == out.lower()), (sample, out)


def test_hello_world():
    assert textkit.slugify("Hello, World!") == "hello-world"


def test_whitespace_runs_collapse_to_one_hyphen():
    assert textkit.slugify("a \t  b") == "a-b"


def test_leading_and_trailing_separators_are_stripped():
    assert textkit.slugify("--Leading and trailing--") == "leading-and-trailing"


def test_idempotent_over_samples():
    for sample in SAMPLES:
        once = textkit.slugify(sample)
        assert textkit.slugify(once) == once, sample


def test_accents_are_kept_transliterated_or_dropped():
    assert textkit.slugify("Café Münster") in {"cafe-munster", "caf-mnster", "café-münster"}


def test_punctuation_only_gives_valid_or_empty():
    out = textkit.slugify("!!!")
    assert out == "" or SLUG_RE.match(out)


def test_non_latin_input_gives_valid_or_empty():
    out = textkit.slugify("東京")
    assert out == "" or SLUG_RE.match(out)
