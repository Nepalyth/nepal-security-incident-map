import pytest

from nepal_incident_map import data

RAW = {
    "id": "L-2026-001", "reported_date": "2026-10-01", "category": "Phishing", "sector": "Government", "organisation": "",
    "title": "Phishing emails reported", "summary": "Officials warned about phishing emails sent to staff.",
    "locations": "Kathmandu;Nationwide", "source_name": "Example News", "source_type": "News media",
    "source_url": "https://example.com/story", "verification": "Reported", "scope": "Sector-wide",
    "service_impact": "None", "data_impact": "None", "loss_npr_million": "", "critical_systems": "false", "notes": "",
}


@pytest.fixture
def store(monkeypatch, tmp_path):
    monkeypatch.setenv(data.DATA_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


def test_store_is_off_unless_configured(monkeypatch):
    monkeypatch.delenv(data.DATA_DIR_ENV_VAR, raising=False)
    assert data.local_store_path() is None and data.read_local_rows() == [] and data.local_store_version() == 0.0
    assert data.append_local_row(RAW) == ["local store is not configured"]


def test_appended_records_are_read_back_and_flow_through_validation(store):
    assert data.append_local_row(RAW) == []
    assert data.append_local_row({**RAW, "id": data.next_local_id(2026), "title": "A second report", "loss_npr_million": "12.5", "critical_systems": "true"}) == []
    rows = data.read_local_rows()
    assert [r["id"] for r in rows] == ["L-2026-001", "L-2026-002"]
    assert data.local_store_version() > 0
    frame = data.build_frame(("local", r) for r in rows).incidents
    assert len(frame) == 2 and set(frame["origin"]) == {"local"}


def test_invalid_records_are_never_written(store):
    problems = data.append_local_row({**RAW, "summary": "Contact ops@example.org about the incident."})
    assert problems and not data.local_store_path().exists()
    assert data.append_local_row({**RAW, "source_url": "http://example.com/x"})
    assert data.read_local_rows() == []


def test_next_local_id_skips_used_numbers(store):
    assert data.next_local_id(2026) == "L-2026-001"
    data.append_local_row(RAW)
    assert data.next_local_id(2026) == "L-2026-002" and data.next_local_id(2027) == "L-2027-001"


def test_admin_requires_both_settings_and_the_right_token(monkeypatch, store):
    monkeypatch.delenv(data.ADMIN_TOKEN_ENV_VAR, raising=False)
    assert not data.admin_enabled() and not data.admin_token_ok("")
    monkeypatch.setenv(data.ADMIN_TOKEN_ENV_VAR, "s3cret")
    assert data.admin_enabled() and data.admin_token_ok("s3cret") and not data.admin_token_ok("s3cre") and not data.admin_token_ok("")


def test_feed_ttl_has_a_floor_and_a_default(monkeypatch):
    monkeypatch.delenv(data.FEED_TTL_ENV_VAR, raising=False)
    assert data.feed_ttl_seconds() == 900
    monkeypatch.setenv(data.FEED_TTL_ENV_VAR, "5")
    assert data.feed_ttl_seconds() == 30
    monkeypatch.setenv(data.FEED_TTL_ENV_VAR, "soon")
    assert data.feed_ttl_seconds() == 900
