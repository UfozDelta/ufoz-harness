def word_wrap(text: str, width: int) -> list[str]:
    """Greedy word wrap: pack whole words into lines no wider than width."""
    lines: list[str] = []
    current = ""
    for word in text.split():
        if not current:
            current = word
        elif len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}"
    if current:
        lines.append(current)
    return lines
