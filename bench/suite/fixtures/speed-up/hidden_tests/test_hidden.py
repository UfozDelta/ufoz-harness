import random
import time

from pairsum import count_pairs


def brute(nums, target):
    return sum(1 for i in range(len(nums)) for j in range(i + 1, len(nums)) if nums[i] + nums[j] == target)


def test_matches_brute_force_on_random_inputs():
    rng = random.Random(7)
    for _ in range(200):
        nums = [rng.randint(-6, 6) for _ in range(rng.randint(0, 30))]
        target = rng.randint(-8, 8)
        assert count_pairs(nums, target) == brute(nums, target), (nums, target)


def test_half_target_duplicates():
    assert count_pairs([5, 5, 5, 5], 10) == 6
    assert count_pairs([0, 0, 0], 0) == 3


def test_does_not_mutate_input():
    nums = [3, 1, 2, 3]
    count_pairs(nums, 4)
    assert nums == [3, 1, 2, 3]


def test_large_input_is_fast():
    rng = random.Random(1)
    nums = [rng.randint(-5000, 5000) for _ in range(30000)]
    start = time.perf_counter()
    result = count_pairs(nums, 100)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, elapsed
    assert isinstance(result, int) and result > 0
