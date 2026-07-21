import feedparser
import trafilatura


def fetch_feed_entries(feed_url: str, limit: int) -> list:
    parsed = feedparser.parse(feed_url)
    return parsed.entries[:limit]


def extract_full_text(url: str, fallback: str = "") -> str:
    """Best-effort full article text; falls back to the feed's own summary."""
    if url:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            text = trafilatura.extract(downloaded)
            if text:
                return text
    return fallback
