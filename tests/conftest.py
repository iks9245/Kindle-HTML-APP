"""Shared fixtures.

The pipeline fetches feeds, calls an LLM and writes a static site, so the tests
drive it against a temporary docs/ tree with both network-facing pieces stubbed.
Everything here is offline and touches nothing in the real repository.
"""
import os
import sys
from datetime import date, datetime

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from digest import config, main, render, state  # noqa: E402

_FEED_XML = '<?xml version="1.0"?><rss version="2.0"><channel><title>{name}</title>{items}</channel></rss>'
_ITEM_XML = "<item><title>{title}</title><link>{link}</link><description>blurb</description></item>"

# Numbered paragraphs so a test can tell which one landed on which page.
ARTICLE_PARAGRAPHS = [f"第{i}段落。" + "字" * 60 for i in range(1, 41)]
ARTICLE_TEXT = "\n\n".join(ARTICLE_PARAGRAPHS)


def write_feed(path, items, name="Test Feed"):
    """Write an RSS file. `items` is an iterable of (title, link)."""
    body = "".join(_ITEM_XML.format(title=t, link=link) for t, link in items)
    with open(path, "w", encoding="utf-8") as f:
        f.write(_FEED_XML.format(name=name, items=body))
    return path


class Site:
    """A temporary docs/ tree plus the knobs to drive build_digest() over it."""

    def __init__(self, root, monkeypatch):
        self.root = root
        self.docs = os.path.join(root, "docs")
        self.feed_path = os.path.join(root, "feed.xml")
        self.config_path = os.path.join(root, "config.yaml")
        self._mp = monkeypatch
        self.today = date(2026, 9, 13)  # a Sunday, so the weekly roundup fires
        # Names of LLM steps that should raise on the next run: any of
        # "summary", "brief", "deep", "quiz", "weekly".
        self.fail = set()
        self.deep_n = 0
        self.day_n = 0

    # -- setup ---------------------------------------------------------------

    def install(self):
        os.makedirs(self.docs, exist_ok=True)
        self.configure()
        write_feed(self.feed_path, self._items())

        mp = self._mp
        mp.setattr(render, "DOCS_DIR", self.docs)
        state_dir = os.path.join(self.root, ".digest-state")
        mp.setattr(state, "_STATE_DIR", state_dir)
        mp.setattr(state, "STATE_PATH", os.path.join(state_dir, "seen.json"))
        mp.setattr(state, "RECENT_PATH", os.path.join(state_dir, "recent.json"))
        mp.setattr(config, "DEFAULT_CONFIG_PATH", self.config_path)

        mp.setattr(main, "extract_full_text", self._extract)
        mp.setattr(main, "summarize_article", self._summary)
        mp.setattr(main, "generate_brief", self._brief)
        mp.setattr(main, "generate_deep_read", self._deep)
        mp.setattr(main, "generate_quiz", self._quiz)
        mp.setattr(main, "generate_weekly_roundup", self._weekly)
        mp.setattr(main, "datetime", self._clock())

    def configure(self, **overrides):
        """Rewrite config.yaml. Keys given here override the defaults below."""
        conf = {
            "language": "zh-TW",
            "timezone": "Asia/Taipei",
            "max_articles_per_feed": 3,
            "quiz_questions": 2,
            "deep_read": "true",
            "weekly_roundup": "true",
            "weekly_roundup_weekday": 6,
            "archive_retention_days": 60,
            "seen_retention_days": 14,
            "article_page_lines": 14,
        }
        conf.update(overrides)
        lines = [f"{k}: {v}" for k, v in conf.items()]
        lines += ["feeds:", "  - name: Test Feed", f"    url: {self.feed_path}",
                  "    category: 科技 Tech"]
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

    def _clock(self):
        site = self

        class FakeDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                d = site.today
                return datetime(d.year, d.month, d.day, 8, 0, tzinfo=tz)

        return FakeDatetime

    # -- stubs ---------------------------------------------------------------

    def _fail_if(self, step):
        if step in self.fail:
            raise RuntimeError(f"stubbed {step} failure (429 rate limit)")

    def _extract(self, url, fallback=""):
        return ARTICLE_TEXT, True

    def _summary(self, title, text, conf, long_form=False):
        self._fail_if("summary")
        return {"summary": f"{title} 摘要", "summary_secondary": "",
                "qa": [{"question": "q", "answer": "a"}]}

    def _brief(self, articles, conf):
        self._fail_if("brief")
        return "今日導讀"

    def _deep(self, article, conf):
        self._fail_if("deep")
        self.deep_n += 1
        return {"background": f"脈絡 #{self.deep_n}", "points": ["重點"],
                "implications": "影響", "glossary": [{"term": "詞", "definition": "解釋"}]}

    def _quiz(self, articles, conf, num_questions):
        self._fail_if("quiz")
        return [{"question": "Q1", "answer": "A1"}]

    def _weekly(self, articles, conf):
        self._fail_if("weekly")
        return {"intro": "本週導言", "themes": [{"title": "主題", "body": "內容"}]}

    # -- driving -------------------------------------------------------------

    def run(self, on=None, fresh_articles=True):
        """Run one build. `on` sets the date; articles are new unless told otherwise."""
        if on is not None:
            self.today = on
        if fresh_articles:
            self.day_n += 1
            write_feed(self.feed_path, self._items())
        main.build_digest()

    # Headlines have to be unlike each other: near-duplicate titles are
    # deliberately collapsed within a run, which would otherwise silently
    # reduce how many articles a fixture produces.
    _HEADLINES = [
        "太空望遠鏡發現新的系外行星",
        "央行宣布維持基準利率不變",
        "研究團隊提出新的半導體製程",
    ]

    def _items(self):
        return [
            (f"{h}（{self.day_n}）", f"http://example.com/{self.day_n}-{i}")
            for i, h in enumerate(self._HEADLINES)
        ]

    # -- inspection ----------------------------------------------------------

    def path(self, *parts):
        return os.path.join(self.docs, *parts)

    def exists(self, *parts):
        return os.path.exists(self.path(*parts))

    def read(self, *parts):
        with open(self.path(*parts), encoding="utf-8") as f:
            return f.read()

    def listdir(self, *parts):
        p = self.path(*parts)
        return sorted(os.listdir(p)) if os.path.isdir(p) else []


@pytest.fixture
def site(tmp_path, monkeypatch):
    s = Site(str(tmp_path), monkeypatch)
    s.install()
    return s
