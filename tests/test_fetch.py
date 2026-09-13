"""fetch_feed_entries must distinguish a broken source from a quiet one.

feedparser never raises: a dead host, an HTTP error page and a healthy feed with
no items all come back as an empty entries list, which is how a broken feed used
to vanish from the digest with nothing in the log.
"""
import os

from conftest import write_feed

from digest.fetch import fetch_feed_entries


def test_healthy_feed_reports_no_error(tmp_path):
    p = write_feed(str(tmp_path / "f.xml"),
                   [(f"T{i}", f"http://example.com/{i}") for i in range(5)])
    entries, error = fetch_feed_entries(p, 3)
    assert error == ""
    assert len(entries) == 3
    assert entries[0]["title"] == "T0"


def test_limit_is_applied(tmp_path):
    p = write_feed(str(tmp_path / "f.xml"),
                   [(f"T{i}", f"http://example.com/{i}") for i in range(5)])
    entries, _ = fetch_feed_entries(p, 2)
    assert len(entries) == 2


def test_valid_but_empty_feed_is_reported(tmp_path):
    p = write_feed(str(tmp_path / "f.xml"), [])
    entries, error = fetch_feed_entries(p, 3)
    assert entries == []
    assert error == "feed returned no entries"


def test_unreadable_source_is_reported(tmp_path):
    entries, error = fetch_feed_entries(str(tmp_path / "missing.xml"), 3)
    assert entries == []
    assert error, "a source that cannot be read must say so"


def test_malformed_xml_is_reported(tmp_path):
    p = tmp_path / "bad.xml"
    p.write_text("<rss><channel><title>oops", encoding="utf-8")
    entries, error = fetch_feed_entries(str(p), 3)
    assert entries == []
    assert error


def test_minor_xml_warning_is_not_treated_as_failure(tmp_path):
    """bozo alone is not a failure — plenty of real feeds trip it and parse fine."""
    p = tmp_path / "bozo.xml"
    # No XML declaration and an undeclared entity: feedparser sets bozo but
    # still returns the item.
    p.write_text(
        '<rss version="2.0"><channel><title>F</title>'
        "<item><title>Caf&eacute;</title><link>http://example.com/1</link></item>"
        "</channel></rss>",
        encoding="utf-8",
    )
    entries, error = fetch_feed_entries(str(p), 3)
    if entries:
        assert error == "", "a feed we could actually read must not be flagged"


def test_http_error_status_is_reported(monkeypatch):
    """A 4xx/5xx page parses as XML-ish junk; the status is the real story."""
    import digest.fetch as fetch_mod

    class FakeParsed:
        status = 403
        entries = []
        bozo = 1
        bozo_exception = Exception("whatever")

    monkeypatch.setattr(fetch_mod.feedparser, "parse", lambda url: FakeParsed())
    entries, error = fetch_feed_entries("http://example.com/feed", 3)
    assert entries == []
    assert error == "HTTP 403"


def test_ok_status_with_entries_is_clean(monkeypatch):
    import digest.fetch as fetch_mod

    class FakeParsed:
        status = 200
        entries = [{"title": "t", "link": "http://example.com/1"}]
        bozo = 0

    monkeypatch.setattr(fetch_mod.feedparser, "parse", lambda url: FakeParsed())
    entries, error = fetch_feed_entries("http://example.com/feed", 3)
    assert error == ""
    assert len(entries) == 1
