"""Navigation tests: no broken links, and the reader's variant sticks.

With no JavaScript, a presentation choice only survives a page load because
every link on a page points at the matching variant. That property is what
these tests pin down — it is easy to break by adding one link that forgets
the suffix, and nothing else would notice.
"""
import os
import re
from datetime import date

import pytest

from digest import render
from digest.strings import strings_for

PREFS_RE = re.compile(r'<p class="prefs">.*?</p>', re.S)
BODY_CLASS_RE = re.compile(r'<body class="([^"]+)"')
HREF_RE = re.compile(r'href="([^"]+)"')


def internal_links(html, *, include_switcher=False):
    """Relative hrefs on a page, excluding the presentation switcher by default."""
    if not include_switcher:
        html = PREFS_RE.sub("", html)
    out = []
    for href in HREF_RE.findall(html):
        if href.startswith(("http://", "https://", "#", "mailto:")):
            continue
        if href.endswith(".css"):  # the stylesheet <link>, not a page to walk
            continue
        out.append(href)
    return out


def crawl(docs, start):
    """Walk every internal link from `start`, returning {rel_path: body class}."""
    seen, queue, missing = {}, [start], []
    while queue:
        rel = queue.pop()
        if rel in seen:
            continue
        path = os.path.join(docs, rel)
        if not os.path.exists(path):
            missing.append(rel)
            continue
        with open(path, encoding="utf-8") as f:
            html = f.read()
        m = BODY_CLASS_RE.search(html)
        seen[rel] = m.group(1) if m else None
        for href in internal_links(html):
            queue.append(os.path.normpath(os.path.join(os.path.dirname(rel), href)))
    return seen, missing


@pytest.fixture
def built(site):
    """A site with a couple of days of content, so archive links have targets."""
    site.run(on=date(2026, 9, 12))
    site.run(on=date(2026, 9, 13))  # Sunday: adds the weekly roundup
    return site


class TestNoBrokenLinks:
    def test_every_internal_link_on_the_site_resolves(self, built):
        broken = []
        for root, _, files in os.walk(built.docs):
            for name in files:
                if not name.endswith(".html"):
                    continue
                path = os.path.join(root, name)
                with open(path, encoding="utf-8") as f:
                    html = f.read()
                for href in internal_links(html, include_switcher=True):
                    target = os.path.normpath(os.path.join(root, href))
                    if not os.path.exists(target):
                        broken.append((os.path.relpath(path, built.docs), href))
        assert broken == []

    def test_every_page_points_at_a_stylesheet_that_exists(self, built):
        for root, _, files in os.walk(built.docs):
            for name in files:
                if not name.endswith(".html"):
                    continue
                with open(os.path.join(root, name), encoding="utf-8") as f:
                    html = f.read()
                m = re.search(r'<link rel="stylesheet" href="([^"]+)"', html)
                assert m, f"{name} has no stylesheet link"
                assert os.path.exists(os.path.normpath(os.path.join(root, m.group(1))))


class TestVariantSticks:
    @pytest.mark.parametrize("start,expected", [
        ("index.html", "f-serif z-medium"),
        ("index-s.html", "f-serif z-small"),
        ("index-l.html", "f-serif z-large"),
        ("index-sans.html", "f-sans z-medium"),
        ("index-sans-s.html", "f-sans z-small"),
        ("index-sans-l.html", "f-sans z-large"),
    ])
    def test_following_links_never_changes_the_variant(self, built, start, expected):
        pages, missing = crawl(built.docs, start)
        assert missing == []
        assert len(pages) > 5, "the crawl should reach more than a couple of pages"
        wrong = {rel: cls for rel, cls in pages.items() if cls != expected}
        assert wrong == {}

    def test_the_crawl_actually_reaches_an_article_page(self, built):
        pages, _ = crawl(built.docs, "index-sans-l.html")
        assert any(rel.startswith("article/") for rel in pages)

    def test_the_crawl_reaches_the_archive_and_companions(self, built):
        pages, _ = crawl(built.docs, "index-l.html")
        assert any(rel.startswith("archive/") for rel in pages)
        assert any(rel.startswith("deepread") for rel in pages)


class TestPageTurns:
    def _first_page(self, site, suffix):
        names = [f for f in site.listdir("article")
                 if f.endswith(suffix) and "-p" not in f]
        assert names, f"no first-page article file ending in {suffix}"
        return names[0]

    def test_next_link_keeps_the_variant(self, built):
        name = self._first_page(built, "-sans-l.html")
        html = built.read("article", name)
        m = re.search(r'class="pager-next" href="([^"]+)"', html)
        assert m, "a multi-page article should have a next link"
        assert m.group(1).endswith("-sans-l.html")
        assert 'class="f-sans z-large"' in built.read("article", m.group(1))

    def test_walking_to_the_last_page_stays_in_variant(self, built):
        name = self._first_page(built, "-sans-l.html")
        seen = 0
        while True:
            html = built.read("article", name)
            assert 'class="f-sans z-large"' in html
            seen += 1
            m = re.search(r'class="pager-next" href="([^"]+)"', html)
            if not m:
                break
            name = m.group(1)
            assert seen < 200, "page chain should terminate"
        assert seen > 1, "the fixture article should span several pages"

    def test_the_last_page_carries_the_follow_up_questions(self, built):
        name = self._first_page(built, ".html")
        while True:
            html = built.read("article", name)
            m = re.search(r'class="pager-next" href="([^"]+)"', html)
            if not m:
                assert "延伸問答" in html
                break
            name = m.group(1)


class TestSizeSwitchKeepsYourPlace:
    def test_switching_size_lands_on_a_page_holding_the_same_paragraph(self, built):
        pages = [f for f in built.listdir("article") if f.endswith("-sans-l.html")]
        multi = sorted(f for f in pages if "-p" in f)
        assert multi, "need a multi-page article for this test"
        name = multi[len(multi) // 2]
        html = built.read("article", name)
        first_para = re.search(r'<p class="fulltext">第(\d+)段落', html).group(1)

        prefs = PREFS_RE.search(html).group(0)
        for target_suffix in ("-sans-s.html", "-sans.html"):
            m = re.search(rf'href="([^"]*{re.escape(target_suffix)})"', prefs)
            assert m, f"switcher should offer {target_suffix}"
            target = built.read("article", m.group(1))
            assert f"第{first_para}段落" in target, (
                f"switching from {name} lost the reader's place"
            )

    def test_the_switcher_marks_the_current_choice(self, built):
        html = built.read("index-sans-l.html")
        prefs = PREFS_RE.search(html).group(0)
        label = strings_for("zh-TW")["sizes"]["large"]
        assert f'<span class="pref-on">{label}</span>' in prefs

    def test_the_family_switch_preserves_the_size(self, built):
        html = built.read("index-sans-l.html")
        prefs = PREFS_RE.search(html).group(0)
        m = re.search(r'class="pref-family" href="([^"]+)"', prefs)
        assert m.group(1) == "index-l.html"
