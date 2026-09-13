"""Pure-function tests: no filesystem, no network, no LLM."""
import json
from datetime import date, timedelta

import pytest

from digest import state
from digest.config import load_config
from digest.dedup import is_similar, normalize_title
from digest.rank import score_article
from digest.summarize import _clip_source, _loads_lenient, _parse_response


class TestDedup:
    def test_normalize_strips_punctuation_and_case(self):
        assert normalize_title("Hello, World!") == "hello world"

    def test_normalize_collapses_whitespace(self):
        assert normalize_title("  a   b\tc ") == "a b c"

    def test_near_duplicate_headlines_match(self):
        a = normalize_title("NASA launches new Mars rover")
        b = normalize_title("NASA Launches New Mars Rover!")
        assert is_similar(a, b)

    def test_unrelated_headlines_do_not_match(self):
        a = normalize_title("NASA launches new Mars rover")
        b = normalize_title("Central bank holds interest rates steady")
        assert not is_similar(a, b)

    def test_empty_never_matches(self):
        assert not is_similar("", "anything")
        assert not is_similar("anything", "")


class TestRank:
    def test_counts_distinct_interest_hits(self):
        article = {"title": "AI and 半導體", "summary": "談 太空"}
        assert score_article(article, ["AI", "半導體", "太空", "經濟"]) == 3

    def test_case_insensitive(self):
        assert score_article({"title": "ai", "summary": ""}, ["AI"]) == 1

    def test_no_interests_scores_zero(self):
        assert score_article({"title": "AI", "summary": "AI"}, []) == 0


class TestConfig:
    def test_missing_keys_get_defaults(self, tmp_path):
        p = tmp_path / "c.yaml"
        p.write_text("language: en\n", encoding="utf-8")
        conf = load_config(str(p))
        assert conf["language"] == "en"
        assert conf["timezone"] == "UTC"
        assert conf["quiz_questions"] == 4
        assert conf["feeds"] == []

    def test_empty_file_is_all_defaults(self, tmp_path):
        p = tmp_path / "c.yaml"
        p.write_text("", encoding="utf-8")
        assert load_config(str(p))["provider"] == "gemini"


class TestLenientJson:
    """The model is asked for bare JSON but does not always comply."""

    def test_plain_object(self):
        assert _loads_lenient('{"a": 1}') == {"a": 1}

    def test_markdown_fenced(self):
        assert _loads_lenient('```json\n{"a": 1}\n```') == {"a": 1}

    def test_bare_fence(self):
        assert _loads_lenient('```\n{"a": 1}\n```') == {"a": 1}

    def test_surrounded_by_prose(self):
        assert _loads_lenient('Sure! Here you go:\n{"a": 1}\nHope that helps.') == {"a": 1}

    def test_unparseable_still_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _loads_lenient("not json at all")


class TestParseResponse:
    def test_extracts_fields_and_caps_qa_at_three(self):
        raw = json.dumps({
            "summary": "  s  ",
            "summary_secondary": "t",
            "qa": [{"question": f"q{i}", "answer": f"a{i}"} for i in range(5)],
        })
        out = _parse_response(raw)
        assert out["summary"] == "s"
        assert out["summary_secondary"] == "t"
        assert len(out["qa"]) == 3

    def test_missing_optional_fields_default_empty(self):
        out = _parse_response('{"summary": "s"}')
        assert out["summary_secondary"] == ""
        assert out["qa"] == []


class TestClipSource:
    def test_short_text_untouched(self):
        assert _clip_source("abc", 100) == "abc"

    def test_long_text_keeps_head_and_tail(self):
        text = "HEAD" + "x" * 5000 + "TAIL"
        out = _clip_source(text, 1000)
        assert out.startswith("HEAD")
        assert out.endswith("TAIL")
        assert "[…]" in out

    def test_stays_within_budget_plus_marker(self):
        out = _clip_source("y" * 9000, 1000)
        assert len(out) <= 1000 + len("\n\n[…]\n\n")

    def test_zero_limit_disables_clipping(self):
        assert _clip_source("abc", 0) == "abc"


class TestStateRetention:
    def test_save_seen_drops_entries_past_retention(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", str(tmp_path))
        monkeypatch.setattr(state, "STATE_PATH", str(tmp_path / "seen.json"))
        today = date.today()
        seen = {
            "http://fresh": today.isoformat(),
            "http://stale": (today - timedelta(days=40)).isoformat(),
        }
        state.save_seen(seen, retention_days=14)
        kept = state.load_seen()
        assert "http://fresh" in kept
        assert "http://stale" not in kept

    def test_zero_retention_keeps_everything(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", str(tmp_path))
        monkeypatch.setattr(state, "STATE_PATH", str(tmp_path / "seen.json"))
        old = (date.today() - timedelta(days=999)).isoformat()
        state.save_seen({"http://ancient": old}, retention_days=0)
        assert "http://ancient" in state.load_seen()

    def test_save_recent_drops_unparseable_and_old_days(self, tmp_path, monkeypatch):
        monkeypatch.setattr(state, "_STATE_DIR", str(tmp_path))
        monkeypatch.setattr(state, "RECENT_PATH", str(tmp_path / "recent.json"))
        today = date.today()
        recent = {
            today.isoformat(): [{"title": "t"}],
            (today - timedelta(days=99)).isoformat(): [{"title": "old"}],
            "not-a-date": [{"title": "junk"}],
        }
        state.save_recent(recent, retention_days=14)
        kept = state.load_recent()
        assert list(kept) == [today.isoformat()]
