# Spec (speed-up): count_pairs is too slow on large inputs

`count_pairs(nums, target)` in the `pairsum` package returns how many index pairs `i < j` satisfy `nums[i] + nums[j] == target`. It is correct but takes far too long on lists of tens of thousands of numbers. Make it fast (it should handle 30,000 numbers in well under a second) without changing what it returns for any input: duplicates count as separate indices, negative numbers and zero are allowed, and an empty or one-element list gives 0.
