from datetime import date, timedelta

import pytest

from nepal_incident_map import data, live, visuals
from nepal_incident_map.schema import validate_record

TODAY = date.today()


def rss(*items: tuple[str, str, str | None, str]) -> bytes:
    """Build an RSS document from (title, link, pubDate or None, source) tuples."""
    body = "".join(
        f"<item><title>{t}</title><link>{link}</link>" + (f"<pubDate>{d}</pubDate>" if d else "") + (f"<source>{s}</source>" if s else "") + "</item>"
        for t, link, d, s in items
    )
    return f"<?xml version='1.0'?><rss version='2.0'><channel>{body}</channel></rss>".encode()


def http_date(day: date) -> str:
    return day.strftime("%a, %d %b %Y 08:00:00 GMT")


@pytest.mark.parametrize("title, category, sector, places", [
    ("Ransomware attack at data centre halts Nepal stock trading", "Ransomware", "Capital markets", ("Nationwide",)),
    ("Government websites hacked and defaced in Nepal", "Defacement", "Government", ("Nationwide",)),
    ("Police warn of phishing SMS targeting bank customers", "Phishing", "Banking & finance", ("Nationwide",)),
    ("DDoS attack takes Kathmandu airport website offline", "Service disruption", "Aviation", ("Kathmandu",)),
    ("Data leak exposes records of a Pokhara hospital", "Data exposure", "Health", ("Pokhara",)),
    ("Online fraud: Rs 3 million stolen from a bank account", "Financial fraud", "Banking & finance", ("Nationwide",)),
])
def test_headlines_are_classified(title, category, sector, places):
    assert live.classify(title) == (category, sector, places)


@pytest.mark.parametrize("title", [
    "Cybersecurity workshop held in Kathmandu", "Hackathon winners announced", "Nepal beat UAE in a thrilling final",
    "Hackers target Nepal", "New cyber policy draft released", "How to avoid phishing: ten tips",
])
def test_non_incidents_are_ignored(title):
    assert live.classify(title) is None


def test_parse_rss_reads_items_and_strips_the_publisher_suffix():
    payload = rss(("Ransomware hits Nepal broker - The Kathmandu Post", "https://example.com/a", http_date(TODAY), "The Kathmandu Post"))
    [item] = live.parse_rss(payload)
    assert item.title == "Ransomware hits Nepal broker" and item.publisher == "The Kathmandu Post" and item.published == TODAY


def test_parse_rss_takes_the_date_from_the_link_when_pubdate_is_missing():
    [item] = live.parse_rss(rss(("Phishing wave", "https://kathmandupost.com/money/2026/10/21/phishing-wave", None, "")))
    assert item.published == date(2026, 10, 21)
    assert live.parse_rss(rss(("No date at all", "https://example.com/story", None, ""))) == []


@pytest.mark.parametrize("payload", [
    b"<!DOCTYPE rss [<!ENTITY a 'x'>]><rss><channel></channel></rss>", b"<rss><channel><!ENTITY x 'y'></channel></rss>", b"not xml",
])
def test_parse_rss_refuses_dtds_and_bad_xml(payload):
    with pytest.raises(ValueError):
        live.parse_rss(payload)


def test_scan_keeps_relevant_items_validates_and_deduplicates():
    recent, old = http_date(TODAY - timedelta(days=3)), http_date(TODAY - timedelta(days=900))
    google = rss(
        ("Ransomware attack halts Nepal stock market - The Kathmandu Post", "https://news.example.com/1", recent, "The Kathmandu Post"),
        ("Ransomware attack halts Nepal stock market! - Republica", "https://news.example.com/2", recent, "Republica"),
        ("Ransomware hits a hospital in Texas - US Daily", "https://news.example.com/3", recent, "US Daily"),
        ("Nepal phishing scam targets bank users - Old News", "https://news.example.com/4", old, "Old News"),
        ("Contact ops@example.org about Nepal ransomware - Mail Wire", "https://news.example.com/5", recent, "Mail Wire"),
    )
    local = rss(("Website defaced after hacking, officials say", "https://kathmandupost.com/national/2026/10/20/website-defaced", None, ""))
    empty = rss()
    result = live.scan(90, fetch=lambda url: local if "kathmandupost" in url else google if "news.google.com" in url else empty)
    assert result.feeds_total == len(live.feeds_for(90)) and result.feeds_ok == result.feeds_total and not result.errors
    titles = {r["title"] for r in result.rows}
    assert "Ransomware attack halts Nepal stock market" in titles and "Website defaced after hacking, officials say" in titles
    assert not any("Texas" in t or "phishing" in t.lower() or "ops@" in t for t in titles)
    assert result.rejected >= 1 and result.duplicates >= 1
    assert all(validate_record(r)[0] is not None for r in result.rows)
    assert [r["reported_date"] for r in result.rows] == sorted((r["reported_date"] for r in result.rows), reverse=True)


def test_scan_survives_feed_failures():
    def failing(url):
        raise ValueError("feed could not be downloaded")

    result = live.scan(30, fetch=failing)
    assert result.feeds_ok == 0 and len(result.errors) == result.feeds_total and result.rows == []


def test_drop_known_removes_repeats_of_curated_incidents():
    rows = [
        {"title": "Ransomware at a brokers data centre halts stock trading", "source_url": "https://a.example/1"},
        {"title": "A completely different phishing story", "source_url": "https://a.example/2"},
        {"title": "Another story", "source_url": "https://curated.example/x"},
    ]
    kept, dropped = live.drop_known(rows, ["Ransomware at a brokers' data centre halts stock trading"], {"https://curated.example/x"})
    assert [r["source_url"] for r in kept] == ["https://a.example/2"] and dropped == 2


def test_live_rows_are_unrated_and_labelled_everywhere():
    [item] = live.parse_rss(rss(("Ransomware attack halts Nepal stock market", "https://news.example.com/1", http_date(TODAY), "Example")))
    row = live.to_row(item, live.PUBLISHER_FEEDS[0])
    frame = data.build_frame([("web", row)]).incidents
    assert frame.loc[0, "severity"] == "Unrated" and frame.loc[0, "score"] == 0 and frame.loc[0, "origin"] == "web"
    for block in (visuals.map_html(frame), visuals.feed_html(frame), visuals.timeline_html(frame)):
        assert "LIVE WEB / UNREVIEWED" in block or "pin" in block
    assert "LIVE WEB / UNREVIEWED" in visuals.timeline_html(frame)
    assert set(data.location_summary(frame)["location"]) == set()
    assert list(data.location_summary(frame).columns) == data.location_summary(frame.iloc[0:0]).columns.tolist()


def test_rated_records_are_unaffected_by_the_assessed_flag():
    frame = data.build_frame(("bundled", r) for r in data.load_seed_rows()).incidents
    assert "Unrated" not in set(frame["severity"]) and frame["score"].min() > 0


def test_live_search_can_be_disabled(monkeypatch):
    monkeypatch.delenv(live.DISABLE_ENV_VAR, raising=False)
    assert live.enabled()
    monkeypatch.setenv(live.DISABLE_ENV_VAR, "1")
    assert not live.enabled()
