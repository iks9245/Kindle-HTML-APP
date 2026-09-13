"""Unit tests for the rendering helpers: pagination, variants, pruning."""
import os
from datetime import date, timedelta

import pytest

from digest import render
from digest.render import (
    DEFAULT_FAMILY,
    DEFAULT_SIZE,
    FAMILIES,
    SIZE_ORDER,
    SIZES,
    VARIANTS,
    _existing_variant,
    _page_for_para,
    _paginate_paragraphs,
    _with_suffix,
    estimate_reading_minutes,
)


class TestVariantNames:
    def test_default_variant_keeps_the_bare_name(self):
        """Old bookmarks and already-generated pages point at the unsuffixed name."""
        assert _with_suffix("index.html", DEFAULT_FAMILY, DEFAULT_SIZE) == "index.html"

    @pytest.mark.parametrize("family,size,expected", [
        ("serif", "small", "index-s.html"),
        ("serif", "large", "index-l.html"),
        ("sans", "medium", "index-sans.html"),
        ("sans", "small", "index-sans-s.html"),
        ("sans", "large", "index-sans-l.html"),
    ])
    def test_suffixes_compose_family_then_size(self, family, size, expected):
        assert _with_suffix("index.html", family, size) == expected

    def test_every_variant_has_a_distinct_name(self):
        names = {_with_suffix("x.html", f, s) for f, s in VARIANTS}
        assert len(names) == len(VARIANTS) == len(FAMILIES) * len(SIZE_ORDER)

    def test_suffix_applies_through_a_subdirectory(self):
        assert _with_suffix("deepread/2026-09-13.html", "sans", "large") == \
            "deepread/2026-09-13-sans-l.html"


class TestPagination:
    def test_returns_index_pairs_covering_every_paragraph(self):
        paras = [f"第{i}段。" + "字" * 40 for i in range(20)]
        pages = _paginate_paragraphs(paras, 14)
        assert pages[0][0] == 0
        assert pages[-1][1] == len(paras)
        for (_, end), (start, _) in zip(pages, pages[1:]):
            assert end == start, "pages must be contiguous with no gaps or overlap"

    def test_paragraphs_are_never_split(self):
        paras = ["short", "also short"]
        pages = _paginate_paragraphs(paras, 100)
        assert pages == [(0, 2)]

    def test_an_overlong_paragraph_gets_its_own_page(self):
        paras = ["tiny", "字" * 4000, "tiny"]
        pages = _paginate_paragraphs(paras, 5)
        assert (1, 2) in pages

    def test_more_lines_per_page_means_fewer_pages(self):
        paras = [f"第{i}段。" + "字" * 60 for i in range(40)]
        assert len(_paginate_paragraphs(paras, 18)) < len(_paginate_paragraphs(paras, 11))

    def test_empty_input_is_one_empty_page(self):
        assert _paginate_paragraphs([], 14) == [(0, 0)]

    def test_non_positive_lines_disables_pagination(self):
        paras = ["a", "b", "c"]
        assert _paginate_paragraphs(paras, 0) == [(0, 3)]


class TestPageForPara:
    def test_finds_the_page_holding_a_paragraph(self):
        pages = [(0, 3), (3, 7), (7, 10)]
        assert _page_for_para(pages, 0) == 1
        assert _page_for_para(pages, 3) == 2
        assert _page_for_para(pages, 6) == 2
        assert _page_for_para(pages, 9) == 3

    def test_out_of_range_clamps_to_the_last_page(self):
        assert _page_for_para([(0, 3), (3, 7)], 99) == 2

    def test_round_trips_across_every_size(self):
        """Switching size must land on a page that really contains the paragraph."""
        paras = [f"第{i}段。" + "字" * 60 for i in range(40)]
        per_size = {
            s: _paginate_paragraphs(paras, max(1, round(14 * SIZES[s]["scale"])))
            for s in SIZE_ORDER
        }
        for src in SIZE_ORDER:
            for page_no, (start, _) in enumerate(per_size[src], 1):
                for dst in SIZE_ORDER:
                    n = _page_for_para(per_size[dst], start)
                    lo, hi = per_size[dst][n - 1]
                    assert lo <= start < hi or start == len(paras)


class TestReadingTime:
    def test_empty_is_zero(self):
        assert estimate_reading_minutes("") == 0

    def test_any_text_is_at_least_one_minute(self):
        assert estimate_reading_minutes("hi") == 1

    def test_longer_text_takes_longer(self):
        short = estimate_reading_minutes("字" * 400)
        long = estimate_reading_minutes("字" * 4000)
        assert long > short

    def test_counts_latin_words_as_well_as_cjk(self):
        assert estimate_reading_minutes(" ".join(["word"] * 3000)) > 5


class TestExistingVariantFallback:
    """Days generated before a variant existed only have the older files."""

    def test_prefers_the_exact_variant(self, tmp_path):
        for name in ("2026-09-13.html", "2026-09-13-sans-l.html"):
            (tmp_path / name).write_text("x", encoding="utf-8")
        assert _existing_variant(str(tmp_path), "2026-09-13.html", "sans", "large") == \
            "2026-09-13-sans-l.html"

    def test_falls_back_to_the_same_family_at_the_default_size(self, tmp_path):
        for name in ("2026-09-13.html", "2026-09-13-sans.html"):
            (tmp_path / name).write_text("x", encoding="utf-8")
        assert _existing_variant(str(tmp_path), "2026-09-13.html", "sans", "large") == \
            "2026-09-13-sans.html"

    def test_falls_back_to_the_default_variant(self, tmp_path):
        (tmp_path / "2026-09-13.html").write_text("x", encoding="utf-8")
        assert _existing_variant(str(tmp_path), "2026-09-13.html", "serif", "large") == \
            "2026-09-13.html"


class TestPruning:
    def _seed(self, d, days_old, extra=""):
        stamp = (date.today() - timedelta(days=days_old)).isoformat()
        for suffix in ("", "-sans", "-l", "-sans-l"):
            (d / f"{stamp}{extra}{suffix}.html").write_text("x", encoding="utf-8")
        return stamp

    def test_prunes_every_variant_of_an_expired_day(self, tmp_path, monkeypatch):
        monkeypatch.setattr(render, "DOCS_DIR", str(tmp_path))
        art = tmp_path / "article"
        art.mkdir()
        old = self._seed(art, 99, extra="-abc123")
        fresh = self._seed(art, 1, extra="-abc123")
        render.prune_old_article_pages(60)
        left = sorted(os.listdir(art))
        assert not any(f.startswith(old) for f in left)
        assert any(f.startswith(fresh) for f in left)

    def test_keeps_index_pages_that_are_not_dated(self, tmp_path, monkeypatch):
        monkeypatch.setattr(render, "DOCS_DIR", str(tmp_path))
        arch = tmp_path / "archive"
        arch.mkdir()
        self._seed(arch, 99)
        for name in ("index.html", "index-sans.html", "index-l.html"):
            (arch / name).write_text("x", encoding="utf-8")
        render.prune_old_archives(60)
        left = sorted(os.listdir(arch))
        assert left == ["index-l.html", "index-sans.html", "index.html"]

    def test_zero_retention_keeps_everything(self, tmp_path, monkeypatch):
        monkeypatch.setattr(render, "DOCS_DIR", str(tmp_path))
        art = tmp_path / "article"
        art.mkdir()
        old = self._seed(art, 9999, extra="-abc123")
        render.prune_old_article_pages(0)
        assert any(f.startswith(old) for f in os.listdir(art))

    def test_missing_directory_is_not_an_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr(render, "DOCS_DIR", str(tmp_path))
        render.prune_old_companion_pages(60)  # no deepread/ or weekly/ yet


class TestStylesheet:
    def test_declares_every_family_and_size(self, tmp_path, monkeypatch):
        monkeypatch.setattr(render, "DOCS_DIR", str(tmp_path))
        render.render_stylesheet()
        css = (tmp_path / render.STYLESHEET).read_text(encoding="utf-8")
        for family in FAMILIES:
            assert f"body.f-{family}" in css
        for size in SIZE_ORDER:
            assert f"body.z-{size}" in css
            assert f"{SIZES[size]['px']}px" in css
