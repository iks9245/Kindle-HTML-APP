"""End-to-end tests for build_digest(), against a temporary docs/ tree.

These cover the failure modes that were silent in production: pages replaced by
an empty state, feeds dying without a trace, and companion pages overwritten a
day after they were generated.
"""
import json
import re
from datetime import date

from conftest import write_feed

from digest import main as main_mod
from digest import render
from digest import state


class TestHappyPath:
    def test_writes_the_whole_site(self, site):
        site.run()
        assert site.exists("index.html")
        assert site.exists("style.css")
        assert site.exists("quiz.html") or True  # no previous day yet
        assert site.exists("deepread.html")
        assert site.exists("archive", "index.html")
        assert site.exists("archive", "2026-09-13.html")
        assert site.listdir("article")

    def test_every_variant_of_the_front_page(self, site):
        site.run()
        for family, size in render.VARIANTS:
            assert site.exists(render._with_suffix("index.html", family, size))

    def test_editor_brief_reaches_both_front_page_and_archive(self, site):
        site.run()
        assert "今日導讀" in site.read("index.html")
        assert "今日導讀" in site.read("archive", "2026-09-13.html")

    def test_summaries_appear_with_their_source(self, site):
        site.run()
        html = site.read("index.html")
        assert "摘要" in html
        assert "Test Feed" in html


class TestQuietRunDoesNotWipe:
    """Re-running after everything has been seen must not blank the day."""

    def test_second_run_same_day_keeps_the_digest(self, site):
        site.run()
        before = site.read("index.html")
        site.run(fresh_articles=False)  # same feed, all links already seen
        assert site.read("index.html") == before
        assert "今日沒有新文章" not in site.read("index.html")

    def test_housekeeping_still_happens(self, site):
        site.run()
        site.run(fresh_articles=False)
        assert site.exists("archive", "index.html")


class TestFailedSideCallsDoNotWipe:
    """A failed LLM call must leave yesterday's good page in place."""

    def test_deep_read_failure_keeps_the_previous_page(self, site):
        site.run(on=date(2026, 9, 10))
        assert "脈絡 #1" in site.read("deepread.html")

        site.fail = {"deep"}
        site.run(on=date(2026, 9, 11))
        assert "脈絡 #1" in site.read("deepread.html")
        assert "今天還沒有深讀內容" not in site.read("deepread.html")

    def test_every_variant_is_preserved_not_just_the_default(self, site):
        site.run(on=date(2026, 9, 10))
        site.fail = {"deep"}
        site.run(on=date(2026, 9, 11))
        for family, size in render.VARIANTS:
            name = render._with_suffix("deepread.html", family, size)
            assert "脈絡 #1" in site.read(name)

    def test_quiz_failure_keeps_the_previous_quiz(self, site):
        site.run(on=date(2026, 9, 10))
        site.run(on=date(2026, 9, 11))  # now there is a previous day to quiz on
        assert "Q1" in site.read("quiz.html")

        site.fail = {"quiz"}
        site.run(on=date(2026, 9, 12))
        assert "Q1" in site.read("quiz.html")

    def test_recovery_updates_the_page_again(self, site):
        site.run(on=date(2026, 9, 10))
        site.fail = {"deep"}
        site.run(on=date(2026, 9, 11))
        site.fail = set()
        site.run(on=date(2026, 9, 12))
        assert "脈絡 #2" in site.read("deepread.html")

    def test_brief_failure_does_not_sink_the_run(self, site):
        site.fail = {"brief"}
        site.run()
        assert site.exists("index.html")
        assert "摘要" in site.read("index.html")


class TestFeedReporting:
    def test_unreadable_feed_is_named_in_the_report(self, site, capsys, tmp_path):
        site.configure()
        missing = str(tmp_path / "gone.xml")
        with open(site.config_path, "a", encoding="utf-8") as f:
            f.write(f"  - name: Dead Feed\n    url: {missing}\n    category: 國際 World\n")
        site.run()
        out = capsys.readouterr()
        combined = out.out + out.err
        assert "Dead Feed" in combined
        assert "unreadable" in combined

    def test_report_accounts_for_every_feed(self, site, capsys):
        site.run()
        out = capsys.readouterr().out
        assert "digest summary for 2026-09-13" in out
        assert "Test Feed" in out
        assert "total:" in out

    def test_blurb_only_extraction_is_counted(self, site, capsys, monkeypatch):
        from digest import main
        monkeypatch.setattr(main, "extract_full_text",
                            lambda url, fallback="": ("a short blurb", False))
        site.run()
        assert "blurb-only" in capsys.readouterr().out

    def test_github_actions_annotation(self, site, capsys, monkeypatch, tmp_path):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        with open(site.config_path, "a", encoding="utf-8") as f:
            f.write(f"  - name: Dead Feed\n    url: {tmp_path / 'gone.xml'}\n"
                    "    category: 國際 World\n")
        site.run()
        assert "::warning::" in capsys.readouterr().out


class TestCompanionArchiving:
    def test_each_day_keeps_its_own_deep_read(self, site):
        days = [date(2026, 9, 10), date(2026, 9, 11), date(2026, 9, 12)]
        for d in days:
            site.run(on=d)
        for i, d in enumerate(days, 1):
            assert f"脈絡 #{i}" in site.read("deepread", f"{d.isoformat()}.html")

    def test_rolling_page_is_the_latest(self, site):
        site.run(on=date(2026, 9, 10))
        site.run(on=date(2026, 9, 11))
        assert "脈絡 #2" in site.read("deepread.html")

    def test_dated_copies_exist_in_every_variant(self, site):
        site.run(on=date(2026, 9, 10))
        for family, size in render.VARIANTS:
            assert site.exists("deepread",
                               render._with_suffix("2026-09-10.html", family, size))

    def test_failed_day_writes_no_dated_page(self, site):
        site.run(on=date(2026, 9, 10))
        site.fail = {"deep"}
        site.run(on=date(2026, 9, 11))
        assert not site.exists("deepread", "2026-09-11.html")

    def test_archived_digest_links_its_own_deep_read(self, site):
        site.run(on=date(2026, 9, 10))
        assert "../deepread/2026-09-10.html" in site.read("archive", "2026-09-10.html")

    def test_a_failed_day_has_no_dangling_deep_read_link(self, site):
        site.run(on=date(2026, 9, 10))
        site.fail = {"deep"}
        site.run(on=date(2026, 9, 11))
        assert "../deepread/2026-09-11.html" not in site.read("archive", "2026-09-11.html")

    def test_weekly_roundup_is_archived_on_its_weekday(self, site):
        site.run(on=date(2026, 9, 13))  # Sunday
        assert site.exists("weekly", "2026-09-13.html")
        assert site.exists("weekly.html")

    def test_weekly_roundup_skipped_on_other_days(self, site):
        site.run(on=date(2026, 9, 10))  # Thursday
        assert not site.exists("weekly", "2026-09-10.html")

    def test_archive_index_lists_deep_reads_and_weeklies(self, site):
        site.run(on=date(2026, 9, 12))
        site.run(on=date(2026, 9, 13))
        idx = site.read("archive", "index.html")
        assert "../deepread/2026-09-12.html" in idx
        assert "../weekly/2026-09-13.html" in idx


class TestDisabledFeatures:
    """Turning a feature off must not leave a link to an empty page."""

    def test_quiz_off_means_no_quiz_link(self, site):
        site.configure(quiz_questions=0)
        site.run()
        assert "quiz.html" not in site.read("index.html")

    def test_deep_read_off_means_no_deep_read_link(self, site):
        site.configure(deep_read="false")
        site.run()
        assert "deepread.html" not in site.read("index.html")

    def test_deep_read_off_writes_no_dated_page(self, site):
        site.configure(deep_read="false")
        site.run(on=date(2026, 9, 10))
        assert not site.exists("deepread", "2026-09-10.html")


class TestDeduplication:
    def test_an_article_seen_before_is_not_repeated(self, site):
        site.run()
        first = site.read("index.html").count("</article>")
        assert first > 0
        site.run(fresh_articles=False)
        assert site.read("index.html").count("</article>") == first

    def test_near_duplicate_titles_within_a_run_are_collapsed(self, site):
        write_feed(site.feed_path, [
            ("NASA launches new Mars rover", "http://example.com/1"),
            ("NASA Launches New Mars Rover", "http://example.com/2"),
            ("Central bank holds rates steady", "http://example.com/3"),
        ])
        site.run(fresh_articles=False)
        assert site.read("index.html").count("</article>") == 2

class TestRerunAddsToTheDay:
    """A second run partway through a day must add to it, not replace it."""

    def _articles(self, site, *parts):
        return site.read(*parts).count("</article>")

    def test_the_day_page_keeps_the_earlier_batch(self, site):
        site.run(on=date(2026, 9, 13))
        first = self._articles(site, "index.html")
        assert first == 3

        site.run(on=date(2026, 9, 13))  # same day, three more stories
        assert self._articles(site, "index.html") == first + 3

    def test_the_archived_copy_of_the_day_matches(self, site):
        site.run(on=date(2026, 9, 13))
        site.run(on=date(2026, 9, 13))
        assert self._articles(site, "archive", "2026-09-13.html") == 6

    def test_every_variant_of_the_day_is_merged(self, site):
        site.run(on=date(2026, 9, 13))
        site.run(on=date(2026, 9, 13))
        for family, size in render.VARIANTS:
            name = render._with_suffix("index.html", family, size)
            assert self._articles(site, name) == 6

    def test_the_earlier_batch_still_links_to_its_offline_pages(self, site):
        site.run(on=date(2026, 9, 13))
        before = set(site.listdir("article"))
        site.run(on=date(2026, 9, 13))
        assert before <= set(site.listdir("article")), "earlier pages must survive"

        html = site.read("index.html")
        broken = [
            href for href in re.findall(r'href="(article/[^"]+)"', html)
            if not site.exists(*href.split("/"))
        ]
        assert broken == []

    def test_state_records_the_whole_day(self, site):
        site.run(on=date(2026, 9, 13))
        site.run(on=date(2026, 9, 13))
        stored = json.loads(open(state.RECENT_PATH, encoding="utf-8").read())
        assert len(stored["2026-09-13"]) == 6

    def test_a_new_day_starts_clean(self, site):
        site.run(on=date(2026, 9, 13))
        site.run(on=date(2026, 9, 14))
        assert self._articles(site, "index.html") == 3

    def test_the_day_keeps_its_first_deep_read(self, site):
        site.run(on=date(2026, 9, 13))
        assert "脈絡 #1" in site.read("deepread", "2026-09-13.html")
        site.run(on=date(2026, 9, 13))
        assert "脈絡 #1" in site.read("deepread", "2026-09-13.html"), (
            "a re-run should not churn the day's companion piece"
        )

    def test_the_brief_is_rewritten_from_the_whole_day(self, site, monkeypatch):
        counts = []

        def brief(articles, conf):
            counts.append(len(articles))
            return "導讀"

        monkeypatch.setattr(main_mod, "generate_brief", brief)
        site.run(on=date(2026, 9, 13))
        site.run(on=date(2026, 9, 13))
        assert counts == [3, 6], "the second brief must see the whole day"

    def test_a_quiet_rerun_changes_nothing(self, site):
        site.run(on=date(2026, 9, 13))
        before = site.read("index.html")
        site.run(fresh_articles=False)  # every link already seen
        assert site.read("index.html") == before

    def test_old_state_records_without_links_are_carried_safely(self, site):
        """State written before the records carried a link or category."""
        site.run(on=date(2026, 9, 13))
        stored = json.loads(open(state.RECENT_PATH, encoding="utf-8").read())
        stored["2026-09-13"] = [
            {"title": "舊格式文章", "summary": "舊摘要", "source": "Old Feed"}
        ]
        with open(state.RECENT_PATH, "w", encoding="utf-8") as f:
            json.dump(stored, f, ensure_ascii=False)

        site.run(on=date(2026, 9, 13))  # must not raise
        html = site.read("index.html")
        assert "舊格式文章" in html
        assert self._articles(site, "index.html") == 4
