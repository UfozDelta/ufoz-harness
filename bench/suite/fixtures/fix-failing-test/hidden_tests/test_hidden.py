import pytest

from textkit import word_wrap


@pytest.mark.parametrize("text, width, expected", [
    ("aaa bbb", 7, ["aaa bbb"]),
    ("the quick brown", 15, ["the quick brown"]),
    ("ab cd ef", 8, ["ab cd ef"]),
    ("x y z w", 7, ["x y z w"]),
    ("hello world", 11, ["hello world"]),
])
def test_line_that_exactly_fills_width_is_kept(text, width, expected):
    assert word_wrap(text, width) == expected


def test_full_line_then_next_word_wraps():
    assert word_wrap("four five six", 9) == ["four five", "six"]


def test_exact_fit_inside_a_paragraph():
    text = "one two three four five six"
    assert word_wrap(text, 9) == ["one two", "three", "four five", "six"]


def test_one_character_over_width_wraps():
    assert word_wrap("aaa bbb", 6) == ["aaa", "bbb"]


def test_single_word_equal_to_width():
    assert word_wrap("abcde", 5) == ["abcde"]


def test_long_word_alone_is_not_split():
    assert word_wrap("supercalifragilistic", 5) == ["supercalifragilistic"]


def test_empty_string_gives_empty_list():
    assert word_wrap("", 7) == []


def test_repeated_spaces_collapse():
    assert word_wrap("a    b", 10) == ["a b"]
