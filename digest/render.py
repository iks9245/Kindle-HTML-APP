import os
from datetime import date, datetime, timedelta

from jinja2 import Environment, FileSystemLoader, select_autoescape

_HERE = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(_HERE, "..", "templates")
DOCS_DIR = os.path.join(_HERE, "..", "docs")

_env = Environment(
    loader=FileSystemLoader(TEMPLATES_DIR),
    autoescape=select_autoescape(["html"]),
)


def _archive_dir() -> str:
    d = os.path.join(DOCS_DIR, "archive")
    os.makedirs(d, exist_ok=True)
    return d


def _existing_dates(exclude: str | None = None) -> list:
    d = _archive_dir()
    dates = sorted(
        f[:-5]
        for f in os.listdir(d)
        if f.endswith(".html") and f != "index.html" and f[:-5] != exclude
    )
    return dates


def _digest_title(date_str: str, language: str) -> str:
    return f"每日 AI 文摘 {date_str}" if language.startswith("zh") else f"Daily AI Digest {date_str}"


def render_digest(date_str: str, categories: dict, conf: dict) -> str:
    prev_dates = _existing_dates(exclude=date_str)
    prev_href = f"{prev_dates[-1]}.html" if prev_dates else None

    tmpl = _env.get_template("digest.html.j2")
    html = tmpl.render(
        title=_digest_title(date_str, conf["language"]),
        generated_at=date_str,
        categories=categories,
        lang=conf["language"],
        home_href="../index.html",
        archive_href="index.html",
        prev_href=prev_href,
    )
    path = os.path.join(_archive_dir(), f"{date_str}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def render_index(date_str: str, categories: dict, conf: dict) -> str:
    tmpl = _env.get_template("digest.html.j2")
    html = tmpl.render(
        title=_digest_title(date_str, conf["language"]),
        generated_at=date_str,
        categories=categories,
        lang=conf["language"],
        home_href=None,
        archive_href="archive/index.html",
        prev_href=None,
    )
    os.makedirs(DOCS_DIR, exist_ok=True)
    path = os.path.join(DOCS_DIR, "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path


def prune_old_archives(retention_days: int) -> None:
    if not retention_days or retention_days <= 0:
        return
    cutoff = date.today() - timedelta(days=retention_days)
    d = _archive_dir()
    for fname in os.listdir(d):
        if not fname.endswith(".html") or fname == "index.html":
            continue
        try:
            file_date = datetime.strptime(fname[:-5], "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            os.remove(os.path.join(d, fname))


def render_archive_index(conf: dict) -> str:
    dates = list(reversed(_existing_dates()))
    tmpl = _env.get_template("archive_index.html.j2")
    html = tmpl.render(
        title="文摘存檔" if conf["language"].startswith("zh") else "Digest Archive",
        lang=conf["language"],
        dates=dates,
    )
    path = os.path.join(_archive_dir(), "index.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path
