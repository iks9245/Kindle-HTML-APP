import hashlib
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import load_config
from .dedup import is_similar, normalize_title
from .fetch import extract_full_text, fetch_feed_entries
from .rank import score_article
from .render import (
    estimate_reading_minutes,
    prune_old_archives,
    prune_old_article_pages,
    render_archive_index,
    render_articles,
    render_deep_read,
    render_digest,
    render_index,
    render_quiz,
    render_weekly,
)
from .state import load_recent, load_seen, save_recent, save_seen
from .summarize import (
    generate_brief,
    generate_deep_read,
    generate_quiz,
    generate_weekly_roundup,
    summarize_article,
)


def _previous_entry(recent: dict, today: str):
    """Most recent stored day strictly before `today` that has articles."""
    days = sorted(d for d, items in recent.items() if d < today and items)
    if not days:
        return None, None
    day = days[-1]
    return recent[day], day


def _week_articles(recent: dict, today: str, days: int = 7):
    """Flatten the last `days` days of stored articles, tagging each with its date."""
    try:
        today_d = datetime.strptime(today, "%Y-%m-%d").date()
    except ValueError:
        return [], ""
    start = today_d - timedelta(days=days - 1)
    out = []
    for day in sorted(recent.keys()):
        try:
            d = datetime.strptime(day, "%Y-%m-%d").date()
        except ValueError:
            continue
        if start <= d <= today_d:
            for a in recent[day]:
                out.append({**a, "date": day})
    label = f"{start.isoformat()} – {today_d.isoformat()}" if out else ""
    return out, label


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
                result = summarize_article(title, text, conf)
            except Exception as exc:
                print(f"warning: skipping {title!r} ({feed['name']}): {exc}", file=sys.stderr)
                continue

            slug = f"{date_str}-{hashlib.sha1((link or title).encode('utf-8')).hexdigest()[:10]}"
            articles.append(
                {
                    "title": title,
                    "link": link,
                    "summary": result["summary"],
                    "summary_secondary": result.get("summary_secondary", ""),
                    "qa": result["qa"],
                    "source": feed["name"],
                    "slug": slug,
                    "full_text": text,
                    "read_minutes": estimate_reading_minutes(text),
                }
            )
            run_titles.append(normalized)
            seen[link] = date_str
        if articles:
            categories.setdefault(feed.get("category", "General"), []).extend(articles)

    for articles in categories.values():
        articles.sort(key=lambda a: -score_article(a, conf["interests"]))

    todays_articles = [
        {"title": a["title"], "summary": a["summary"], "source": a["source"]}
        for articles in categories.values()
        for a in articles
    ]

    # Editor's brief: one short cross-article overview of the day, baked into
    # both today's front page and its archived copy.
    brief = ""
    if todays_articles and conf["editor_brief"]:
        try:
            brief = generate_brief(todays_articles, conf)
        except Exception as exc:
            print(f"warning: editor brief failed: {exc}", file=sys.stderr)

    # Deep read: pick the meatiest article of the day (most full text to work
    # with) and generate a longer companion piece on its own page.
    deep = None
    deep_article = None
    all_articles = [a for articles in categories.values() for a in articles]
    if all_articles and conf["deep_read"]:
        deep_article = max(all_articles, key=lambda a: len(a.get("full_text", "")))
        try:
            result = generate_deep_read(deep_article, conf)
            if result["background"] or result["points"] or result["implications"] or result["glossary"]:
                deep = result
        except Exception as exc:
            print(f"warning: deep read failed: {exc}", file=sys.stderr)

    # Recall quiz: questions come from the previous day's articles (spaced
    # review), and today's articles are stashed for tomorrow's quiz.
    recent = load_recent()
    prev_articles, prev_date = _previous_entry(recent, date_str)
    quiz_items: list = []
    if prev_articles and conf["quiz_questions"] > 0:
        try:
            quiz_items = generate_quiz(prev_articles, conf, conf["quiz_questions"])
        except Exception as exc:
            print(f"warning: quiz generation failed: {exc}", file=sys.stderr)
    if todays_articles:
        recent[date_str] = todays_articles

    # Weekly roundup: once a week, theme up the last 7 days from recent state.
    # Only regenerated on the roundup weekday; other days keep the last one.
    roundup = None
    week_label = ""
    if conf["weekly_roundup"] and datetime.now(tz).weekday() == conf["weekly_roundup_weekday"]:
        week_arts, week_label = _week_articles(recent, date_str)
        if week_arts:
            try:
                result = generate_weekly_roundup(week_arts, conf)
                if result["intro"] or result["themes"]:
                    roundup = result
            except Exception as exc:
                print(f"warning: weekly roundup failed: {exc}", file=sys.stderr)

    render_articles(date_str, categories, conf)
    render_digest(date_str, categories, conf, brief=brief)
    if roundup:
        render_weekly(roundup, week_label, conf)
    render_index(date_str, categories, conf, brief=brief)
    render_quiz(quiz_items, prev_date, conf)
    render_deep_read(deep, deep_article, conf)
    prune_old_archives(conf["archive_retention_days"])
    prune_old_article_pages(conf["archive_retention_days"])
    render_archive_index(conf)
    save_seen(seen, conf["seen_retention_days"])
    save_recent(recent, conf["seen_retention_days"])


if __name__ == "__main__":
    build_digest()
