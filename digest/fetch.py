import feedparser
import trafilatura

# Below this many characters we treat an "extraction" as failed and fall back
# to the feed's own summary — real article bodies are longer, and short results
# are usually paywall walls or navigation boilerplate rather than content.
MIN_FULLTEXT_CHARS = 400


def fetch_feed_entries(feed_url: str, limit: int) -> list:
    parsed = feedparser.parse(feed_url)
    return parsed.entries[:limit]


def extract_full_text(url: str, fallback: str = "") -> tuple[str, bool]:
    """Best-effort full article text.

    Returns ``(text, extracted)`` where ``extracted`` is True only when we got a
    real article body from the page. On failure (or too-short results) it falls
    back to the feed's own summary with ``extracted`` False, so callers can tell
    a full read apart from a one-line blurb.
    """
    if url:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text and len(text) >= MIN_FULLTEXT_CHARS:
                return text, True
    return fallback, False
