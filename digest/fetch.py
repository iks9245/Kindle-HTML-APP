import feedparser
import trafilatura

# Below this many characters we treat an "extraction" as failed and fall back
# to the feed's own summary — real article bodies are longer, and short results
# are usually paywall walls or navigation boilerplate rather than content.
MIN_FULLTEXT_CHARS = 400


def fetch_feed_entries(feed_url: str, limit: int) -> tuple[list, str]:
    """Newest entries from a feed, plus a short description of what went wrong.

    feedparser never raises: a dead host, an HTTP error page and a healthy feed
    that simply has no items all come back as an empty ``entries`` list. That is
    why a broken source used to just vanish from the digest with no trace in the
    log. The second element is ``""`` when the fetch looks fine and a one-line
    problem description otherwise, so callers can report it.

    ``bozo`` on its own is not treated as a failure — plenty of real feeds parse
    fine while tripping a minor XML warning — so it is only reported when it
    left us with nothing to read.
    """
    parsed = feedparser.parse(feed_url)

    status = getattr(parsed, "status", None)
    if isinstance(status, int) and status >= 400:
        return [], f"HTTP {status}"

    entries = parsed.entries[:limit]
    if not entries:
        exc = getattr(parsed, "bozo_exception", None)
        if exc:
            return [], f"{type(exc).__name__}: {exc}"
        return [], "feed returned no entries"
    return entries, ""


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
