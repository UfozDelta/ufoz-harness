from pairsum import count_pairs


def test_basic():
    assert count_pairs([1, 2, 3, 4], 5) == 2


def test_duplicates_are_separate_indices():
    assert count_pairs([2, 2, 2], 4) == 3


def test_negatives_and_zero():
    assert count_pairs([-1, 1, 0, 0], 0) == 2


def test_empty_and_single():
    assert count_pairs([], 3) == 0
    assert count_pairs([3], 3) == 0
