import os
import re
from datetime import date, datetime, timedelta

from jinja2 import Environment, FileSystemLoader, select_autoescape

_HERE = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(_HERE, "..", "templates")
DOCS_DIR = os.path.join(_HERE, "..", "docs")

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)

# Kindle's browser can't reliably load custom web fonts, so "more fonts"
# means picking between generic font-family stacks. Each one is rendered as
# its own static page (suffix on the filename) rather than a CSS toggle,
# because the font-size switcher already uses the URL's #fragment via
# :target — a page can only have one active fragment at a time, so a second
# independent toggle can't share that mechanism.
FONTS = {
    "serif": {"suffix": "", "label": "襯線字體", "family": 'Georgia, "Times New Roman", serif'},
    "sans": {"suffix": "-sans", "label": "無襯線字體", "family": "Helvetica, Arial, sans-serif"},
}


def _other_font(font: str) -> str:
    return "sans" if font == "serif" else "serif"


def _with_suffix(html_name: str, font: str) -> str:
    suffix = FONTS[font]["suffix"]
    if not suffix:
        return html_name
    return html_name[: -len(".html")] + suffix + ".html"


def _archive_dir() -> str:
    d = os.path.join(DOCS_DIR, "archive")
    os.makedirs(d, exist_ok=True)
    return d


def _article_dir() -> str:
    d = os.path.join(DOCS_DIR, "article")
    os.makedirs(d, exist_ok=True)
    return d


def _split_paragraphs(text: str) -> list:
    return [line.strip() for line in text.splitlines() if line.strip()]


_CJK_RE = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]")
_LATIN_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def estimate_reading_minutes(text: str) -> int:
    """Rough minutes-to-read across CJK (per char) and Latin (per word) text."""
    if not text:
        return 0
    cjk = len(_CJK_RE.findall(text))
    latin_words = len(_LATIN_WORD_RE.findall(text))
    minutes = cjk / 350 + latin_words / 220
    return max(1, round(minutes))


def _existing_dates(exclude: str | None = None) -> list:
    """Canonical (serif-filename) dates only — font variants share these dates."""
    d = _archive_dir()
    dates = []
    for f in os.listdir(d):
        if not f.endswith(".html") or f.endswith("-sans.html") or f == "index.html":
            continue
        name = f[: -len(".html")]
        if name == exclude:
            continue
        dates.append(name)
    return sorted(dates)


def _digest_title(date_str: str, language: str) -> str:
    return f"每日 AI 文摘 {date_str}" if language.startswith("zh") else f"Daily AI Digest {date_str}"


def render_digest(date_str: str, categories: dict, conf: dict, brief: str = "") -> None:
    prev_dates = _existing_dates(exclude=date_str)
    prev_base = f"{prev_dates[-1]}.html" if prev_dates else None

    tmpl = _env.get_template("digest.html.j2")
    for font in FONTS:
        other = _other_font(font)
        html = tmpl.render(
            title=_digest_title(date_str, conf["language"]),
            generated_at=date_str,
            categories=categories,
            brief=brief,
            lang=conf["language"],
            home_href=_with_suffix("../index.html", font),
            archive_href=_with_suffix("index.html", font),
            prev_href=_with_suffix(prev_base, font) if prev_base else None,
            font_family=FONTS[font]["family"],
            font_href=_with_suffix(f"{date_str}.html", other),
            font_label=FONTS[other]["label"],
            article_prefix="../article/",
            font_suffix=FONTS[font]["suffix"],
        )
        path = os.path.join(_archive_dir(), _with_suffix(f"{date_str}.html", font))
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)


def render_index(date_str: str, categories: dict, conf: dict, brief: str = "") -> None:
    os.makedirs(DOCS_DIR, exist_ok=True)
    tmpl = _env.get_template("digest.html.j2")
    for font in FONTS:
        other = _other_font(font)
        html = tmpl.render(
            title=_digest_title(date_str, conf["language"]),
            generated_at=date_str,
            categories=categories,
            brief=brief,
            lang=conf["language"],
            home_href=None,
            archive_href=_with_suffix("archive/index.html", font),
            prev_href=None,
            font_family=FONTS[font]["family"],
            font_href=_with_suffix("index.html", other),
            font_label=FONTS[other]["label"],
            article_prefix="article/",
            font_suffix=FONTS[font]["suffix"],
            quiz_href=_with_suffix("quiz.html", font),
            deepread_href=_with_suffix("deepread.html", font),
        )
        path = os.path.join(DOCS_DIR, _with_suffix("index.html", font))
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)


def render_articles(date_str: str, categories: dict, conf: dict) -> None:
    """One offline full-text page per article, in each font variant.

    Filenames are prefixed with the digest date so they can be pruned on the
    same schedule as the archive pages that link to them.
    """
    tmpl = _env.get_template("article.html.j2")
    for articles in categories.values():
        for a in articles:
            slug = a.get("slug")
            if not slug:
                continue
            paragraphs = _split_paragraphs(a.get("full_text", ""))
            base_name = f"{slug}.html"
            for font in FONTS:
                other = _other_font(font)
                html = tmpl.render(
                    title=a["title"],
                    lang=conf["language"],
                    source=a["source"],
                    original_link=a["link"],
                    paragraphs=paragraphs,
                    qa=a.get("qa"),
                    read_minutes=a.get("read_minutes"),
                    home_href=_with_suffix("../index.html", font),
                    archive_href=_with_suffix("../archive/index.html", font),
                    font_family=FONTS[font]["family"],
                    font_href=_with_suffix(base_name, other),
                    font_label=FONTS[other]["label"],
                )
                path = os.path.join(_article_dir(), _with_suffix(base_name, font))
                with open(path, "w", encoding="utf-8") as f:
                    f.write(html)


def prune_old_article_pages(retention_days: int) -> None:
    if not retention_days or retention_days <= 0:
        return
    cutoff = date.today() - timedelta(days=retention_days)
    d = _article_dir()
    for fname in os.listdir(d):
        if not fname.endswith(".html"):
            continue
        try:
            file_date = datetime.strptime(fname[:10], "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            os.remove(os.path.join(d, fname))


def prune_old_archives(retention_days: int) -> None:
    if not retention_days or retention_days <= 0:
        return
    cutoff = date.today() - timedelta(days=retention_days)
    d = _archive_dir()
    for fname in os.listdir(d):
        if not fname.endswith(".html") or fname in ("index.html", "index-sans.html"):
            continue
        base = fname[: -len(".html")]
        if base.endswith("-sans"):
            base = base[: -len("-sans")]
        try:
            file_date = datetime.strptime(base, "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            os.remove(os.path.join(d, fname))


def render_quiz(quiz_items: list, source_date: str | None, conf: dict) -> None:
    """A single rolling recall-quiz page (docs/quiz.html) in each font variant."""
    os.makedirs(DOCS_DIR, exist_ok=True)
    zh = conf["language"].startswith("zh")
    title = "昨日回顧小考" if zh else "Daily Recall Quiz"
    tmpl = _env.get_template("quiz.html.j2")
    for font in FONTS:
        other = _other_font(font)
        html = tmpl.render(
            title=title,
            lang=conf["language"],
            quiz=quiz_items,
            source_date=source_date,
            home_href=_with_suffix("index.html", font),
            archive_href=_with_suffix("archive/index.html", font),
            font_family=FONTS[font]["family"],
            font_href=_with_suffix("quiz.html", other),
            font_label=FONTS[other]["label"],
        )
        path = os.path.join(DOCS_DIR, _with_suffix("quiz.html", font))
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)


def render_deep_read(deep: dict | None, article: dict | None, conf: dict) -> None:
    """A single rolling 'deep read of the day' page (docs/deepread.html)."""
    os.makedirs(DOCS_DIR, exist_ok=True)
    zh = conf["language"].startswith("zh")
    title = "每日深讀" if zh else "Deep Read of the Day"
    tmpl = _env.get_template("deepread.html.j2")
    for font in FONTS:
        other = _other_font(font)
        article_href = None
        if article and article.get("slug"):
            article_href = _with_suffix(f"article/{article['slug']}.html", font)
        html = tmpl.render(
            title=title,
            lang=conf["language"],
            deep=deep,
            article_title=article["title"] if article else None,
            article_href=article_href,
            original_link=article["link"] if article else None,
            home_href=_with_suffix("index.html", font),
            archive_href=_with_suffix("archive/index.html", font),
            font_family=FONTS[font]["family"],
            font_href=_with_suffix("deepread.html", other),
            font_label=FONTS[other]["label"],
        )
        path = os.path.join(DOCS_DIR, _with_suffix("deepread.html", font))
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)


def render_archive_index(conf: dict) -> None:
    dates = list(reversed(_existing_dates()))
    tmpl = _env.get_template("archive_index.html.j2")
    for font in FONTS:
        other = _other_font(font)
        date_links = [(d, _with_suffix(f"{d}.html", font)) for d in dates]
        html = tmpl.render(
            title="文摘存檔" if conf["language"].startswith("zh") else "Digest Archive",
            lang=conf["language"],
            date_links=date_links,
            home_href=_with_suffix("../index.html", font),
            font_family=FONTS[font]["family"],
            font_href=_with_suffix("index.html", other),
            font_label=FONTS[other]["label"],
        )
        path = os.path.join(_archive_dir(), _with_suffix("index.html", font))
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
