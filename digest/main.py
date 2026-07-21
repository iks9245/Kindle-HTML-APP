from datetime import datetime
from zoneinfo import ZoneInfo

from .config import load_config
from .fetch import extract_full_text, fetch_feed_entries
from .render import render_archive_index, render_digest, render_index
from .summarize import summarize_article


def build_digest() -> None:
    conf = load_config()
    tz = ZoneInfo(conf["timezone"])
    date_str = datetime.now(tz).strftime("%Y-%m-%d")

    categories: dict[str, list] = {}
    for feed in conf["feeds"]:
        entries = fetch_feed_entries(feed["url"], conf["max_articles_per_feed"])
        articles = []
        for entry in entries:
            title = entry.get("title", "Untitled")
            link = entry.get("link", "")
            fallback = entry.get("summary", "")
            text = extract_full_text(link, fallback)
            if not text:
                continue
            summary = summarize_article(title, text, conf["language"], conf["model"])
            articles.append({"title": title, "link": link, "summary": summary, "source": feed["name"]})
        if articles:
            categories.setdefault(feed.get("category", "General"), []).extend(articles)

    render_digest(date_str, categories, conf)
    render_index(date_str, categories, conf)
    render_archive_index(conf)


if __name__ == "__main__":
    build_digest()
