"""Smaller correctness details that are easy to regress silently.

Each of these pins something that was wrong or undocumented: the date the
workflow labels its commit with, what the seen-state actually dedupes, which
provider gets an output cap, and what happens when extraction blows up.
"""
import os
import re
from datetime import date, datetime, timezone

import pytest

from conftest import write_feed

from digest import main as main_mod
from digest import summarize


class TestCommitDateMatchesContent:
    """`date -u` in the workflow labelled a 22:00 UTC run with the day before."""

    def test_the_emitted_date_is_the_digest_date(self, site, tmp_path, monkeypatch):
        out = tmp_path / "gh_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        site.run(on=date(2026, 9, 13))
        assert out.read_text(encoding="utf-8").strip() == "date=2026-09-13"

    def test_the_label_names_a_day_that_was_actually_written(self, site, tmp_path, monkeypatch):
        out = tmp_path / "gh_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        site.run(on=date(2026, 9, 13))
        emitted = out.read_text(encoding="utf-8").strip().split("=", 1)[1]
        assert site.exists("archive", f"{emitted}.html")

    def test_the_date_follows_the_configured_timezone_not_utc(self, site, tmp_path, monkeypatch):
        """The 22:00 UTC schedule is already the next day in Asia/Taipei — which
        is the whole reason `date -u` in the workflow was wrong."""
        out = tmp_path / "gh_output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        site.run_at_utc(datetime(2026, 9, 13, 22, 0, tzinfo=timezone.utc))
        assert out.read_text(encoding="utf-8").strip() == "date=2026-09-14"
        assert site.exists("archive", "2026-09-14.html")

    def test_it_is_emitted_even_when_the_run_finds_nothing(self, site, tmp_path, monkeypatch):
        out = tmp_path / "gh_output"
        site.run(on=date(2026, 9, 13))
        monkeypatch.setenv("GITHUB_OUTPUT", str(out))
        site.run(fresh_articles=False)  # quiet run, returns early
        assert "date=2026-09-13" in out.read_text(encoding="utf-8")

    def test_nothing_is_written_outside_actions(self, site, monkeypatch):
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
        site.run()  # must not raise

    def test_the_workflow_uses_the_step_output(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(root, ".github/workflows/daily-digest.yml"), encoding="utf-8") as f:
            wf = f.read()
        assert "id: digest" in wf
        assert "steps.digest.outputs.date" in wf


class TestCrossRunDedupIsByUrl:
    """What config.yaml now says: across runs, only an identical URL is caught."""

    def test_the_same_url_is_not_summarized_twice(self, site):
        site.run()
        first = site.read("index.html").count("</article>")
        site.run(fresh_articles=False)
        assert site.read("index.html").count("</article>") == first

    def test_a_near_duplicate_title_is_collapsed_within_one_run(self, site):
        write_feed(site.feed_path, [
            ("NASA launches new Mars rover", "http://example.com/a"),
            ("NASA Launches New Mars Rover", "http://example.com/b"),
        ])
        site.run(fresh_articles=False)
        assert site.read("index.html").count("</article>") == 1

    def test_but_not_across_runs_when_the_url_differs(self, site):
        """Two feeds' copies of one story have different URLs, so day two can
        still show the other one. Documented, not accidental."""
        write_feed(site.feed_path, [("NASA launches new Mars rover", "http://example.com/a")])
        site.run(on=date(2026, 9, 12), fresh_articles=False)
        assert site.read("index.html").count("</article>") == 1

        write_feed(site.feed_path, [("NASA Launches New Mars Rover", "http://example.com/b")])
        site.run(on=date(2026, 9, 13), fresh_articles=False)
        assert site.read("index.html").count("</article>") == 1, (
            "a different URL is a new article across runs"
        )


class TestOutputCapIsOpenAiOnly:
    """Gemini 2.5 spends output budget on reasoning first, so a cap sized for a
    non-thinking model can leave nothing. The asymmetry is deliberate."""

    def _conf(self, provider):
        return {"provider": provider, "model": "m", "language": "en"}

    def test_openai_receives_the_cap(self, monkeypatch):
        seen = {}

        class FakeOpenAI:
            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        seen.update(kwargs)
                        class R:
                            choices = [type("C", (), {"message": type("M", (), {"content": "{}"})})]
                        return R()

        monkeypatch.setattr(summarize, "_get_openai_client", lambda base_url: FakeOpenAI)
        summarize._complete("p", self._conf("openai"), openai_max_tokens=123)
        assert seen["max_tokens"] == 123

    def test_gemini_is_not_given_a_cap(self, monkeypatch):
        seen = {}

        class FakeGemini:
            class models:
                @staticmethod
                def generate_content(**kwargs):
                    seen.update(kwargs)
                    return type("R", (), {"text": "{}"})

        monkeypatch.setattr(summarize, "_get_gemini_client", lambda: FakeGemini)
        summarize._complete("p", self._conf("gemini"), openai_max_tokens=123)
        config = seen.get("config", {})
        assert "max_output_tokens" not in config
        assert "123" not in str(config)

    def test_an_unknown_provider_is_rejected(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            summarize._complete("p", self._conf("llama-at-home"), openai_max_tokens=1)


class TestExtractionFailureDoesNotSinkTheRun:
    def test_a_raising_extractor_falls_back_to_the_feed_summary(self, site, monkeypatch, capsys):
        def boom(url, fallback=""):
            raise RuntimeError("connection reset by peer")

        monkeypatch.setattr(main_mod, "extract_full_text", boom)
        site.run()
        # The feed's <description> is "blurb", so articles survive as blurbs.
        assert site.exists("index.html")
        assert site.read("index.html").count("</article>") > 0
        out = capsys.readouterr()
        assert "extraction failed" in out.out + out.err

    def test_those_articles_are_counted_as_blurb_only(self, site, monkeypatch, capsys):
        monkeypatch.setattr(
            main_mod, "extract_full_text",
            lambda url, fallback="": (_ for _ in ()).throw(RuntimeError("boom")),
        )
        site.run()
        report = capsys.readouterr().out
        blurbs = int(re.search(r"(\d+) blurb-only", report).group(1))
        assert blurbs > 0

    def test_an_empty_fallback_skips_the_article_rather_than_crashing(self, site, monkeypatch):
        write_feed(site.feed_path, [("A story", "http://example.com/x")])
        # Strip the <description> so there is no fallback text at all.
        raw = open(site.feed_path, encoding="utf-8").read().replace(
            "<description>blurb</description>", ""
        )
        open(site.feed_path, "w", encoding="utf-8").write(raw)
        monkeypatch.setattr(
            main_mod, "extract_full_text",
            lambda url, fallback="": (_ for _ in ()).throw(RuntimeError("boom")),
        )
        site.run(fresh_articles=False)  # must not raise
