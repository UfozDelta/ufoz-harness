def count_pairs(nums: list[int], target: int) -> int:
    """Count index pairs i < j with nums[i] + nums[j] == target."""
    total = 0
    for i in range(len(nums)):
        for j in range(i + 1, len(nums)):
            if nums[i] + nums[j] == target:
                total += 1
    return total
