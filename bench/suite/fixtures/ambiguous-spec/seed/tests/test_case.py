from textkit import title_case


def test_capitalises_each_word():
    assert title_case("hello world") == "Hello World"


def test_lowercases_rest_of_word():
    assert title_case("hELLO wORLD") == "Hello World"


def test_collapses_whitespace():
    assert title_case("  a   b ") == "A B"


def test_empty_string():
    assert title_case("") == ""
