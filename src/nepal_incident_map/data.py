"""Load, validate and merge incident records from the bundled dataset and authorised feeds."""

from __future__ import annotations

import csv
import hmac
import io
import ipaddress
import json
import os
import socket
import threading
import urllib.error
import urllib.request
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from importlib import resources
from pathlib import Path
from urllib.parse import urlparse

import nepali_datetime
import pandas as pd

from nepal_incident_map.geo import GAZETTEER
from nepal_incident_map.schema import Incident, check_source_url, score_parts, severity_of, validate_record

MAX_FEED_BYTES = 2_000_000
MAX_FEED_ROWS = 2_000
FEED_ENV_VAR = "INCIDENT_FEED_URLS"
FEED_TTL_ENV_VAR = "INCIDENT_FEED_TTL"
DATA_DIR_ENV_VAR = "INCIDENT_DATA_DIR"
ADMIN_TOKEN_ENV_VAR = "INCIDENT_ADMIN_TOKEN"

CSV_COLUMNS = [
    "id", "reported_date", "category", "sector", "organisation", "title", "summary", "locations", "source_name", "source_type",
    "source_url", "verification", "scope", "service_impact", "data_impact", "loss_npr_million", "critical_systems", "notes",
]
_write_lock = threading.Lock()

COLUMNS = [
    "id", "date", "year", "category", "sector", "organisation", "title", "summary", "locations", "source_name",
    "source_type", "source_url", "verification", "scope", "service_impact", "data_impact", "loss_npr_million",
    "critical_systems", "notes", "score", "severity", "origin",
]

# Sourced context events drawn on the timeline.
MILESTONES = [(date(2024, 1, 23), "National Cyber Security Centre approved by Cabinet", "NCSC approved")]

# Nepal Police Cyber Bureau registered cases, as reported by The Kathmandu Post (22 July 2025).
CYBER_BUREAU_STATS = pd.DataFrame({
    "fiscal_year": ["2023/24", "2024/25"],
    "registered_cases": [19_730, 18_926],
    "financial_fraud": [4_112, 7_723],
})
CYBER_BUREAU_SOURCE = "https://kathmandupost.com/national/2025/07/22/nepal-recorded-52-daily-cybercrime-cases-last-fiscal"


@dataclass(frozen=True)
class Rejection:
    origin: str
    record: str
    problems: tuple[str, ...]


@dataclass(frozen=True)
class LoadResult:
    incidents: pd.DataFrame
    rejected: list[Rejection]


@lru_cache(maxsize=1)
def load_provinces() -> dict[str, list[list[list[float]]]]:
    """Simplified province outlines: geoBoundaries NPL ADM1 (CC BY 3.0 IGO; Survey Department of Nepal, OCHA)."""
    return json.loads(resources.files("nepal_incident_map").joinpath("data/nepal_provinces.json").read_text("utf-8"))


@lru_cache(maxsize=1)
def load_world_dots() -> dict[str, list[list[float]]]:
    """Dotted world land for the globe, sampled from Natural Earth 110m land (public domain)."""
    return json.loads(resources.files("nepal_incident_map").joinpath("data/world_dots.json").read_text("utf-8"))


def load_seed_rows() -> list[dict[str, str]]:
    text = resources.files("nepal_incident_map").joinpath("data/incidents.csv").read_text("utf-8")
    return list(csv.DictReader(io.StringIO(text)))


def local_store_path() -> Path | None:
    """Opt-in writable store: only exists when the operator sets INCIDENT_DATA_DIR."""
    base = os.environ.get(DATA_DIR_ENV_VAR, "").strip()
    return Path(base).expanduser() / "incidents_local.csv" if base else None


def local_store_version() -> float:
    """Modification time, used as a cache key so new records appear on the next page load."""
    path = local_store_path()
    return path.stat().st_mtime if path and path.exists() else 0.0


def read_local_rows() -> list[dict[str, str]]:
    path = local_store_path()
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def admin_enabled() -> bool:
    return local_store_path() is not None and bool(os.environ.get(ADMIN_TOKEN_ENV_VAR))


def admin_token_ok(supplied: str) -> bool:
    expected = os.environ.get(ADMIN_TOKEN_ENV_VAR, "")
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


def next_local_id(year: int) -> str:
    used = {row.get("id", "") for row in read_local_rows()}
    number = 1
    while f"L-{year}-{number:03d}" in used:
        number += 1
    return f"L-{year}-{number:03d}"


def _incident_row(incident: Incident) -> dict[str, str]:
    return {
        "id": incident.id, "reported_date": incident.reported_date.isoformat(), "category": incident.category, "sector": incident.sector,
        "organisation": incident.organisation, "title": incident.title, "summary": incident.summary, "locations": ";".join(incident.locations),
        "source_name": incident.source_name, "source_type": incident.source_type, "source_url": incident.source_url,
        "verification": incident.verification, "scope": incident.scope, "service_impact": incident.service_impact,
        "data_impact": incident.data_impact, "loss_npr_million": "" if incident.loss_npr_million is None else f"{incident.loss_npr_million:g}",
        "critical_systems": "true" if incident.critical_systems else "false", "notes": incident.notes,
    }


def append_local_row(raw: Mapping[str, object]) -> list[str]:
    """Validate with the same rules as every other source, then append. Returns the problems (empty on success)."""
    path = local_store_path()
    if path is None:
        return ["local store is not configured"]
    incident, problems = validate_record(raw)
    if incident is None:
        return problems
    with _write_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        fresh = not path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            if fresh:
                writer.writeheader()
            writer.writerow(_incident_row(incident))
    return []


def feed_ttl_seconds() -> int:
    try:
        return max(30, int(os.environ.get(FEED_TTL_ENV_VAR, "900")))
    except ValueError:
        return 900


def build_frame(rows: Iterable[tuple[str, Mapping[str, object]]]) -> LoadResult:
    """Validate (origin, row) pairs and return the accepted records plus the rejected ones."""
    records: list[dict[str, object]] = []
    rejected: list[Rejection] = []
    seen: set[str] = set()
    for origin, raw in rows:
        incident, problems = validate_record(raw)
        label = str(raw.get("id") or "(no id)")[:40]
        if incident is not None and incident.id in seen:
            incident, problems = None, ["id: duplicate of an earlier record"]
        if incident is None:
            rejected.append(Rejection(origin, label, tuple(problems)))
            continue
        seen.add(incident.id)
        score = sum(points for _, points in score_parts(
            incident.scope, incident.service_impact, incident.data_impact,
            incident.loss_npr_million, incident.critical_systems,
        )) if incident.assessed else 0
        records.append({
            "id": incident.id, "date": pd.Timestamp(incident.reported_date), "year": incident.reported_date.year,
            "category": incident.category, "sector": incident.sector, "organisation": incident.organisation,
            "title": incident.title, "summary": incident.summary, "locations": incident.locations,
            "source_name": incident.source_name, "source_type": incident.source_type,
            "source_url": incident.source_url, "verification": incident.verification, "scope": incident.scope,
            "service_impact": incident.service_impact, "data_impact": incident.data_impact,
            "loss_npr_million": incident.loss_npr_million, "critical_systems": incident.critical_systems,
            "notes": incident.notes, "score": score, "severity": severity_of(score), "origin": origin,
        })
    frame = pd.DataFrame(records, columns=COLUMNS)
    frame["date"] = pd.to_datetime(frame["date"])
    return LoadResult(frame.sort_values("date", ascending=False, ignore_index=True), rejected)


def parse_feed(data: bytes, filename: str) -> list[dict[str, object]]:
    """Parse a CSV or JSON feed into raw rows. Raises ValueError for anything unusable."""
    if len(data) > MAX_FEED_BYTES:
        raise ValueError("Feed is larger than 2 MB")
    text = data.decode("utf-8-sig")
    if filename.lower().endswith(".json") or text.lstrip().startswith(("[", "{")):
        payload = json.loads(text)
        rows = payload.get("incidents") if isinstance(payload, dict) else payload
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError("JSON feed must be a list of incident objects")
    else:
        rows = list(csv.DictReader(io.StringIO(text)))
    if len(rows) > MAX_FEED_ROWS:
        raise ValueError(f"Feed has more than {MAX_FEED_ROWS} records")
    return rows


def configured_feed_urls() -> list[str]:
    """Feed URLs set by the operator through the environment; never taken from the UI."""
    return [u.strip() for u in os.environ.get(FEED_ENV_VAR, "").split(",") if u.strip()]


class _SameHostRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only when it stays on the already-vetted https host."""

    def __init__(self, host: str):
        self.host = host

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if check_source_url(newurl) is None and urlparse(newurl).hostname == self.host:
            return super().redirect_request(req, fp, code, msg, headers, newurl)
        return None


def fetch_feed(url: str, timeout: float = 10.0) -> bytes:
    """Download an operator-configured feed over https from a public host; redirects must stay on that host."""
    if (problem := check_source_url(url)) is not None:
        raise ValueError(problem.replace("source_url", "feed URL"))
    host = urlparse(url).hostname or ""
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise ValueError("feed host could not be resolved") from exc
    if not addresses or not all(ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("feed host must resolve to public addresses only")
    opener = urllib.request.build_opener(_SameHostRedirect(host))
    request = urllib.request.Request(url, headers={
        "Accept": "text/csv, application/json, application/rss+xml, application/xml",
        "User-Agent": "NepalCyberIncidentMap/0.1 (public headline reader)",
    })
    try:
        with opener.open(request, timeout=timeout) as response:
            payload = response.read(MAX_FEED_BYTES + 1)
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ValueError("feed could not be downloaded") from exc
    if len(payload) > MAX_FEED_BYTES:
        raise ValueError("Feed is larger than 2 MB")
    return payload


def bs_label(day: date | pd.Timestamp) -> str:
    """Bikram Sambat rendering such as '2083 Aswin 5'; empty when the date is out of range."""
    try:
        bs = nepali_datetime.date.from_datetime_date(day.date() if isinstance(day, pd.Timestamp) else day)
    except (ValueError, OverflowError):
        return ""
    return f"{bs.year} {bs.strftime('%B')} {bs.day}"


def location_summary(df: pd.DataFrame) -> pd.DataFrame:
    """One row per gazetteer location with incident count, worst severity score and hover lines."""
    rows: list[dict[str, object]] = []
    for item in df.sort_values("date", ascending=False).itertuples():
        for loc in item.locations:
            if loc in GAZETTEER:
                rows.append({
                    "location": loc, "score": item.score,
                    "line": f"{item.date:%d %b %Y} | {item.category} | {item.severity}: {item.title}",
                })
    if not rows:
        return pd.DataFrame(columns=["location", "lat", "lon", "province", "count", "score", "lines", "severity"])
    grouped = pd.DataFrame(rows).groupby("location", sort=False).agg(
        count=("score", "size"), score=("score", "max"), lines=("line", list),
    ).reset_index()
    grouped["lat"] = grouped["location"].map(lambda k: GAZETTEER[k][0])
    grouped["lon"] = grouped["location"].map(lambda k: GAZETTEER[k][1])
    grouped["province"] = grouped["location"].map(lambda k: GAZETTEER[k][2])
    grouped["severity"] = grouped["score"].map(severity_of)
    return grouped


def unplotted_count(df: pd.DataFrame) -> int:
    """Incidents with no city-level location (nationwide or sector-wide)."""
    return int(sum(not any(loc in GAZETTEER for loc in locs) for locs in df["locations"])) if len(df) else 0
