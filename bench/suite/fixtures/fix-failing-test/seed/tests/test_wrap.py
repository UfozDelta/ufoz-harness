from textkit import word_wrap


def test_short_text_stays_on_one_line():
    assert word_wrap("hi there", 20) == ["hi there"]


def test_empty_text_gives_no_lines():
    assert word_wrap("", 10) == []


def test_wraps_when_words_do_not_fit():
    assert word_wrap("aa bb cc dd", 4) == ["aa", "bb", "cc", "dd"]


def test_long_word_stays_on_its_own_line():
    assert word_wrap("extraordinary cat", 5) == ["extraordinary", "cat"]


def test_wraps_long_sentence():
    assert word_wrap("the quick brown fox jumps", 10) == ["the quick", "brown fox", "jumps"]
