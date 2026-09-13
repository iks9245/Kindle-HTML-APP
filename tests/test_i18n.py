"""The generated pages must be entirely in the configured language.

`language` is free-form and feeds the model, so summaries come back in whatever
was asked for. The page furniture is translated from digest/strings.py, and the
risk is a leftover hardcoded string or a key that silently resolves to nothing.
"""
import glob
import os
import re
import string
from datetime import date

import pytest

from digest.strings import FALLBACK, STRINGS, strings_for

TEMPLATES = glob.glob(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "*.j2")
)
# CJK ranges — enough to spot Chinese furniture leaking into an English page.
CJK_RE = re.compile(r"[　-〿㐀-䶿一-鿿＀-￯]")


class TestResolution:
    @pytest.mark.parametrize("tag", ["zh", "zh-TW", "zh_CN", "ZH-tw", " zh-TW "])
    def test_chinese_variants_all_resolve_to_chinese(self, tag):
        assert strings_for(tag) is STRINGS["zh"]

    @pytest.mark.parametrize("tag", ["en", "en-GB", "EN"])
    def test_english_variants_resolve_to_english(self, tag):
        assert strings_for(tag) is STRINGS["en"]

    @pytest.mark.parametrize("tag", ["ja", "fr", "de-CH", "klingon", "", None])
    def test_untranslated_languages_fall_back(self, tag):
        """English navigation around Japanese summaries beats Chinese navigation."""
        assert strings_for(tag) is STRINGS[FALLBACK]


class TestTableIntegrity:
    def test_every_language_defines_the_same_keys(self):
        reference = set(STRINGS[FALLBACK])
        for tag, table in STRINGS.items():
            assert set(table) == reference, f"{tag} has a different key set"

    def test_nested_tables_match_too(self):
        for nested in ("families", "sizes"):
            reference = set(STRINGS[FALLBACK][nested])
            for tag, table in STRINGS.items():
                assert set(table[nested]) == reference, f"{tag}.{nested} differs"

    def test_placeholders_are_preserved_across_translations(self):
        """A translation that drops {minutes} would raise at render time."""
        def holders(value):
            return {f for _, f, _, _ in string.Formatter().parse(value) if f}

        for key, ref in STRINGS[FALLBACK].items():
            if not isinstance(ref, str):
                continue
            for tag, table in STRINGS.items():
                assert holders(table[key]) == holders(ref), f"{tag}[{key!r}] placeholders differ"

    def test_no_value_is_empty(self):
        for tag, table in STRINGS.items():
            for key, value in table.items():
                if isinstance(value, str):
                    assert value.strip(), f"{tag}[{key!r}] is blank"


class TestTemplatesOnlyUseRealKeys:
    """Jinja renders an unknown attribute as empty text, so a typo is silent."""

    def _referenced_keys(self):
        found = set()
        for path in TEMPLATES:
            with open(path, encoding="utf-8") as f:
                body = f.read()
            found |= set(re.findall(r"\bt\.([a-z_]+)", body))
            found |= set(re.findall(r"""\bt\[["']([a-z_]+)["']\]""", body))
        return found

    def test_templates_reference_at_least_the_main_keys(self):
        referenced = self._referenced_keys()
        assert {"home", "archive", "original"} <= referenced

    def test_every_key_a_template_uses_exists_in_every_language(self):
        referenced = self._referenced_keys()
        for tag, table in STRINGS.items():
            missing = sorted(referenced - set(table))
            assert missing == [], f"{tag} is missing {missing}"


class TestNoHardcodedTextLeftInTemplates:
    def test_templates_contain_no_cjk(self):
        """All display text must come from the string table, separators included."""
        offenders = {}
        for path in TEMPLATES:
            with open(path, encoding="utf-8") as f:
                hits = CJK_RE.findall(f.read())
            if hits:
                offenders[os.path.basename(path)] = "".join(sorted(set(hits)))
        assert offenders == {}


class TestRenderedPages:
    def _nav(self, html):
        """The furniture: everything outside article bodies and summaries."""
        html = re.sub(r"<h3>.*?</h3>", "", html, flags=re.S)
        html = re.sub(r'<p class="summary.*?</p>', "", html, flags=re.S)
        html = re.sub(r'<p class="fulltext">.*?</p>', "", html, flags=re.S)
        html = re.sub(r"<details>.*?</details>", "", html, flags=re.S)
        html = re.sub(r'<div class="brief">.*?</div>', "", html, flags=re.S)
        return html

    def test_no_page_anywhere_shows_chinese(self, site):
        """With every piece of content ASCII, any CJK left is a furniture leak.

        Walks the whole generated site rather than a couple of pages, so a
        renderer that forgets to consult the string table cannot hide in a
        page type the test didn't happen to name.
        """
        site.configure(language="en")
        site.use_ascii_content()
        site.run(on=date(2026, 9, 12))
        site.run(on=date(2026, 9, 13))  # Sunday: brings in the weekly roundup

        offenders = {}
        pages = 0
        for root, _, files in os.walk(site.docs):
            for name in files:
                if not name.endswith(".html"):
                    continue
                pages += 1
                with open(os.path.join(root, name), encoding="utf-8") as f:
                    hits = CJK_RE.findall(f.read())
                if hits:
                    rel = os.path.relpath(os.path.join(root, name), site.docs)
                    offenders[rel] = "".join(sorted(set(hits)))
        assert pages > 20, "expected the crawl to cover the whole site"
        assert offenders == {}

    def test_english_config_uses_english_wording(self, site):
        site.configure(language="en")
        site.run()
        html = site.read("index.html")
        assert "Daily AI Digest" in html
        assert "Home" in html or "Archive" in html
        assert 'lang="en"' in html

    def test_english_article_pages_are_english(self, site):
        site.configure(language="en")
        site.use_ascii_content()
        site.run()
        name = [f for f in site.listdir("article") if f.endswith(".html")][0]
        nav = self._nav(site.read("article", name))
        assert CJK_RE.findall(nav) == []
        assert "Next" in nav or "Previous" in nav

    def test_chinese_config_still_produces_chinese(self, site):
        site.run()
        html = site.read("index.html")
        assert "每日 AI 文摘" in html
        assert "首頁" in html or "存檔列表" in html
        assert 'lang="zh-TW"' in html

    def test_untranslated_language_gets_english_furniture(self, site):
        """Japanese summaries, English navigation — not Chinese navigation."""
        site.configure(language="ja")
        site.use_ascii_content()
        site.run()
        nav = self._nav(site.read("index.html"))
        assert "首頁" not in nav
        assert "Home" in nav or "Archive" in nav
        assert 'lang="ja"' in site.read("index.html")

    def test_switcher_labels_follow_the_language(self, site):
        site.configure(language="en")
        site.run()
        prefs = re.search(r'<p class="prefs">.*?</p>', site.read("index.html"), re.S).group(0)
        assert "Switch to" in prefs
        assert CJK_RE.findall(prefs) == []

    def test_deep_read_headings_follow_the_language(self, site):
        site.configure(language="en")
        site.run()
        html = site.read("deepread.html")
        assert "Background" in html
        assert "Glossary" in html

    def test_interpolated_strings_render_their_values(self, site):
        site.configure(language="en")
        site.run()
        name = [f for f in site.listdir("article") if "-p2" in f and f.endswith("-p2.html")]
        assert name, "expected a multi-page article"
        html = site.read("article", name[0])
        assert re.search(r"Page \d+ of \d+", html), "page_of placeholders not filled"
        assert "{page}" not in html and "{total}" not in html
