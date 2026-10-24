from datetime import date

import pytest

from nepal_incident_map.schema import check_source_url, score_parts, severity_label, validate_record

GOOD = {
    "id": "T-1", "reported_date": "2026-01-05", "category": "Phishing", "sector": "Government",
    "organisation": "", "title": "Phishing emails reported", "summary": "Officials warned about phishing emails sent to staff.",
    "locations": "Kathmandu", "source_name": "Example News", "source_type": "News media",
    "source_url": "https://example.com/story", "verification": "Reported", "scope": "Sector-wide",
    "service_impact": "None", "data_impact": "None", "loss_npr_million": "", "critical_systems": "false", "notes": "",
}


def check(**overrides):
    return validate_record({**GOOD, **overrides})


def test_valid_record_is_accepted():
    incident, problems = check()
    assert problems == []
    assert incident is not None and incident.reported_date == date(2026, 1, 5)


@pytest.mark.parametrize("field, value, fragment", [
    ("summary", "Contact ops@example.org for details of the breach.", "email"),
    ("summary", "The attacker used 203.0.113.9 to reach the server.", "IP address"),
    ("summary", "Victims were called from 9841234567 repeatedly.", "phone"),
    ("summary", "Details published at https://paste.example/abc today.", "URL"),
    ("summary", "The affected portal was reachable at moha.gov.np for hours.", "URL"),
    ("summary", "The sample hash is d41d8cd98f00b204e9800998ecf8427e for review.", "hash"),
    ("summary", "The dump listed password: hunter2 for the admin account.", "credential"),
    ("summary", "A working proof-of-concept was circulated to the public.", "exploit"),
    ("title", "<script>alert(1)</script>", "markup"),
])
def test_unsafe_content_is_rejected(field, value, fragment):
    incident, problems = check(**{field: value})
    assert incident is None
    assert any(fragment in p for p in problems)


@pytest.mark.parametrize("field, value", [
    ("category", "Espionage"), ("verification", "Rumour"), ("locations", "Atlantis"), ("locations", ""),
    ("reported_date", "05/01/2026"), ("reported_date", "2999-01-01"), ("source_url", "http://example.com/x"),
    ("source_url", "https://127.0.0.1/x"), ("source_url", "https://user:pw@example.com/x"),
    ("loss_npr_million", "-4"), ("critical_systems", "maybe"), ("id", "x"),
])
def test_invalid_fields_are_rejected(field, value):
    incident, problems = check(**{field: value})
    assert incident is None and problems


def test_multiple_locations_and_case_insensitive_enums():
    incident, _ = check(locations="kathmandu; Pokhara;Nationwide", category="phishing")
    assert incident.locations == ("Kathmandu", "Pokhara", "Nationwide")
    assert incident.category == "Phishing"


@pytest.mark.parametrize("score, label", [(0, "Low"), (2, "Low"), (3, "Medium"), (4, "Medium"), (5, "High"), (6, "Critical"), (11, "Critical")])
def test_severity_thresholds(score, label):
    assert severity_label(score) == label


def test_score_parts_sum():
    parts = score_parts("National-level", "Outage", "Large-scale", 120.0, True)
    assert sum(p for _, p in parts) == 3 + 2 + 2 + 3 + 1


def test_loss_tiers():
    total = lambda loss: dict(score_parts("Single organisation", "None", "None", loss, False))["Financial loss"]
    assert [total(None), total(0.5), total(1), total(10), total(99.9), total(100)] == [0, 0, 1, 2, 2, 3]


def test_check_source_url_accepts_public_https():
    assert check_source_url("https://kathmandupost.com/a/b") is None
    assert check_source_url("https://localhost/a") is not None
