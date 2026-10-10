from collections import Counter


def count_pairs(nums: list[int], target: int) -> int:
    """Count index pairs i < j with nums[i] + nums[j] == target."""
    counts = Counter(nums)
    total = 0
    for value, n in counts.items():
        other = target - value
        if other == value:
            total += n * (n - 1) // 2
        elif value < other and other in counts:
            total += n * counts[other]
    return total
