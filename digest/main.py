import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import load_config
from .dedup import is_similar, normalize_title
from .fetch import extract_full_text, fetch_feed_entries
from .render import prune_old_archives, render_archive_index, render_digest, render_index
from .state import load_seen, save_seen
from .summarize import summarize_article


def build_digest() -> None:
    conf = load_config()
    tz = ZoneInfo(conf["timezone"])
    date_str = datetime.now(tz).strftime("%Y-%m-%d")

    seen = load_seen()
    run_titles: list[str] = []  # normalized titles already picked this run

    categories: dict[str, list] = {}
    for feed in conf["feeds"]:
        entries = fetch_feed_entries(feed["url"], conf["max_articles_per_feed"])
        articles = []
        for entry in entries:
            title = entry.get("title", "Untitled")
            link = entry.get("link", "")

            if link in seen:
                continue
            normalized = normalize_title(title)
            if any(is_similar(normalized, t) for t in run_titles):
                continue

            fallback = entry.get("summary", "")
            text = extract_full_text(link, fallback)
            if not text:
                continue
            try:
                summary = summarize_article(title, text, conf)
            except Exception as exc:
                print(f"warning: skipping {title!r} ({feed['name']}): {exc}", file=sys.stderr)
                continue

            articles.append({"title": title, "link": link, "summary": summary, "source": feed["name"]})
            run_titles.append(normalized)
            seen[link] = date_str
        if articles:
            categories.setdefault(feed.get("category", "General"), []).extend(articles)

    render_digest(date_str, categories, conf)
    render_index(date_str, categories, conf)
    prune_old_archives(conf["archive_retention_days"])
    render_archive_index(conf)
    save_seen(seen, conf["seen_retention_days"])


if __name__ == "__main__":
    build_digest()
