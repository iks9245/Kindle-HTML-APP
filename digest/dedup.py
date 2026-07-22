import difflib
import re

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)

SIMILARITY_THRESHOLD = 0.75


def normalize_title(title: str) -> str:
    cleaned = _PUNCT_RE.sub("", title.lower())
    return " ".join(cleaned.split())


def is_similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() >= SIMILARITY_THRESHOLD
