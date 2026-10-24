import json
import socket

import pytest

from nepal_incident_map import data

ROW = {
    "id": "T-1", "reported_date": "2026-01-05", "category": "Phishing", "sector": "Government", "organisation": "",
    "title": "Phishing emails reported", "summary": "Officials warned about phishing emails sent to staff.",
    "locations": "Kathmandu", "source_name": "Example News", "source_type": "News media",
    "source_url": "https://example.com/story", "verification": "Reported", "scope": "Sector-wide",
    "service_impact": "None", "data_impact": "None", "loss_npr_million": "", "critical_systems": "false", "notes": "",
}


def test_bundled_dataset_is_fully_valid():
    result = data.build_frame(("bundled", r) for r in data.load_seed_rows())
    assert result.rejected == []
    frame = result.incidents
    assert len(frame) == 11
    assert frame["id"].is_unique
    assert frame["date"].is_monotonic_decreasing


def test_bundled_severities_follow_the_rubric():
    frame = data.build_frame(("bundled", r) for r in data.load_seed_rows()).incidents.set_index("id")
    assert frame.loc["NP-2026-004", "severity"] == "Critical"
    assert frame.loc["NP-2017-001", "severity"] == "High"
    assert frame.loc["NP-2025-002", "severity"] == "Medium"


def test_duplicates_and_bad_rows_are_rejected_with_reasons():
    rows = [("a", ROW), ("b", ROW), ("c", {**ROW, "id": "T-2", "summary": "Mail ops@example.org now."})]
    result = data.build_frame(rows)
    assert list(result.incidents["id"]) == ["T-1"]
    assert [r.record for r in result.rejected] == ["T-1", "T-2"]
    assert "duplicate" in result.rejected[0].problems[0]


def test_empty_input_gives_typed_empty_frame():
    frame = data.build_frame([]).incidents
    assert frame.empty and list(frame.columns) == data.COLUMNS


def test_parse_feed_csv_and_json():
    csv_text = ",".join(ROW) + "\n" + ",".join(f'"{v}"' for v in ROW.values())
    assert data.parse_feed(csv_text.encode(), "feed.csv")[0]["id"] == "T-1"
    assert data.parse_feed(json.dumps({"incidents": [ROW]}).encode(), "feed.json")[0]["id"] == "T-1"
    assert data.parse_feed(json.dumps([ROW]).encode(), "feed.txt")[0]["id"] == "T-1"


@pytest.mark.parametrize("payload, name", [(b'{"incidents": "nope"}', "f.json"), (b"[1, 2]", "f.json"), (b"x" * 2_000_001, "f.csv")])
def test_parse_feed_rejects_bad_input(payload, name):
    with pytest.raises(ValueError):
        data.parse_feed(payload, name)


def test_fetch_feed_refuses_unsafe_targets(monkeypatch):
    with pytest.raises(ValueError):
        data.fetch_feed("http://example.com/feed.csv")
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [(0, 0, 0, "", ("10.0.0.5", 443))])
    with pytest.raises(ValueError, match="public"):
        data.fetch_feed("https://feeds.example.com/feed.csv")


def test_configured_feed_urls(monkeypatch):
    monkeypatch.setenv(data.FEED_ENV_VAR, " https://a.example/x.csv , ,https://b.example/y.json ")
    assert data.configured_feed_urls() == ["https://a.example/x.csv", "https://b.example/y.json"]


def test_location_summary_and_unplotted_count():
    frame = data.build_frame(("bundled", r) for r in data.load_seed_rows()).incidents
    summary = data.location_summary(frame).set_index("location")
    assert summary.loc["Kathmandu", "count"] == 7
    assert {"Biratnagar", "Simara", "Nepalgunj", "Bhairahawa"} <= set(summary.index)
    assert summary.loc["Kathmandu", "severity"] == "Critical"
    assert data.unplotted_count(frame) == 4


def test_bs_label():
    import datetime

    assert data.bs_label(datetime.date(2026, 9, 21)) == "2083 Aswin 5"
    assert data.bs_label(datetime.date(1800, 1, 1)) == ""
