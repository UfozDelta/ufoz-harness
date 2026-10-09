import re
import unicodedata


def slugify(text: str) -> str:
    """Turn text into a lower-case ASCII slug with words joined by hyphens."""
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
