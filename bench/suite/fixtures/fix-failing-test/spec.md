# Spec (fix-failing-test): word_wrap pushes exact-width lines to the next line

`word_wrap(text, width)` in the `textkit` package packs words into lines greedily. A line that is exactly `width` characters long gets pushed onto the next line, which is wrong. Our test suite fails on this check:

    assert word_wrap("aaa bbb", 7) == ["aaa bbb"]

Please fix `word_wrap` so a line may fill the width exactly. Lines must never be wider than `width`, except that a single word longer than `width` stays on its own line unsplit. Runs of whitespace act as one separator, and empty text gives an empty list.
