# Spec (ambiguous-spec): add a slugify helper to textkit

Our site builds article URLs from titles, so we need a helper that turns a title into a slug. Please add `slugify` to the `textkit` package so that `from textkit import slugify` works. Some of our titles are in French, German and Japanese, so it should handle unicode sensibly.
