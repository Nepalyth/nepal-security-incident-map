"""Controlled vocabularies, the severity rubric and record validation.

The schema deliberately has no field for threat-actor names, indicators of compromise, exploit
details or personal data, so none can be published through this dashboard.
"""

from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from urllib.parse import urlparse

from nepal_incident_map.geo import GAZETTEER, NATIONWIDE

CATEGORIES = ("Ransomware", "Data exposure", "Phishing", "Defacement", "Service disruption", "Financial fraud")
SECTORS = (
    "Government", "Banking & finance", "Capital markets", "Fintech & payments", "Aviation",
    "Telecom", "Energy", "Education", "Health", "Media", "Other",
)
VERIFICATION = ("Confirmed", "Reported", "Claimed")
SOURCE_TYPES = ("Official statement", "Law enforcement / regulator", "News media", "Security researcher", "Authorized feed")
SEVERITIES = ("Low", "Medium", "High", "Critical")

VERIFICATION_HELP = {
    "Confirmed": "Acknowledged by the affected organisation, a regulator or law enforcement.",
    "Reported": "Covered by credible media or researchers; no official statement seen.",
    "Claimed": "A claim made by a third party and not independently confirmed. Hidden by default.",
}

SCOPE_POINTS = {"Single organisation": 1, "Sector-wide": 2, "National-level": 3}
SERVICE_POINTS = {"None": 0, "Degraded": 1, "Outage": 2}
DATA_POINTS = {"None": 0, "Limited": 1, "Large-scale": 2}
LOSS_TIERS_NPR_MILLION = ((100.0, 3), (10.0, 2), (1.0, 1))

_UNSAFE_PATTERNS = {
    "an email address": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "an IP address": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "a phone number": re.compile(r"(?<!\d)(?:\+?977[-\s]?)?9[78]\d{8}(?!\d)"),
    "a URL or hostname": re.compile(r"https?://|\bwww\.|\b[\w-]+(?:\.[\w-]+)*\.np\b", re.I),
    "a file hash": re.compile(r"\b[a-f0-9]{32,64}\b", re.I),
    "credential material": re.compile(r"\b(?:pass(?:word)?|pwd|token|api[_-]?key)\s*[:=]\s*\S+", re.I),
    "exploit detail": re.compile(r"\b(?:proof[- ]of[- ]concept|poc|exploit code|payload|shellcode|reverse shell)\b", re.I),
    "markup": re.compile(r"[<>]"),
}
_ID = re.compile(r"^[A-Za-z0-9._:-]{3,40}$")
_TRUE = {"true", "yes", "y", "1"}
_FALSE = {"", "false", "no", "n", "0"}
_MIN_DATE = date(2000, 1, 1)


@dataclass(frozen=True)
class Incident:
    id: str
    reported_date: date
    category: str
    sector: str
    organisation: str
    title: str
    summary: str
    locations: tuple[str, ...]
    source_name: str
    source_type: str
    source_url: str
    verification: str
    scope: str
    service_impact: str
    data_impact: str
    loss_npr_million: float | None
    critical_systems: bool
    notes: str


def score_parts(
    scope: str, service_impact: str, data_impact: str, loss_npr_million: float | None, critical_systems: bool,
) -> list[tuple[str, int]]:
    """Transparent severity rubric: each factor contributes points that sum to the score."""
    loss_points = next((pts for floor, pts in LOSS_TIERS_NPR_MILLION if (loss_npr_million or 0) >= floor), 0)
    return [
        (f"Scope: {scope}", SCOPE_POINTS[scope]),
        (f"Service impact: {service_impact}", SERVICE_POINTS[service_impact]),
        (f"Data impact: {data_impact}", DATA_POINTS[data_impact]),
        ("Financial loss", loss_points),
        ("Core operational systems affected", 1 if critical_systems else 0),
    ]


def severity_label(score: int) -> str:
    if score >= 6:
        return "Critical"
    if score == 5:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


def _text(value: object) -> str:
    if value is None or (isinstance(value, float) and value != value):
        return ""
    return " ".join(str(value).split())


def _choice(value: object, options: Iterable[str], field: str, problems: list[str]) -> str:
    text = _text(value)
    for option in options:
        if text.casefold() == option.casefold():
            return option
    problems.append(f"{field}: '{text[:40]}' is not allowed")
    return ""


def _check_text(value: str, field: str, limit: int, problems: list[str]) -> None:
    if len(value) > limit:
        problems.append(f"{field}: longer than {limit} characters")
    for label, pattern in _UNSAFE_PATTERNS.items():
        if pattern.search(value):
            problems.append(f"{field}: contains {label}, which this dataset does not publish")


def check_source_url(url: str) -> str | None:
    """Return a problem description, or None when the URL is an acceptable public https link."""
    if len(url) > 300:
        return "source_url: too long"
    parts = urlparse(url)
    host = (parts.hostname or "").lower()
    if parts.scheme != "https" or not host:
        return "source_url: must be an https link"
    if parts.username or parts.password:
        return "source_url: must not embed credentials"
    if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
        return "source_url: must be a public host"
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return None
    return "source_url: must use a hostname, not an IP address"


def _locations(value: object, problems: list[str]) -> tuple[str, ...]:
    raw = value if isinstance(value, (list, tuple)) else str(value or "").split(";")
    names: list[str] = []
    for item in raw:
        name = _text(item)
        if not name:
            continue
        match = next((k for k in (*GAZETTEER, NATIONWIDE) if k.casefold() == name.casefold()), None)
        if match is None:
            problems.append(f"locations: '{name[:30]}' is not in the city-level gazetteer")
        elif match not in names:
            names.append(match)
    if not names:
        problems.append("locations: at least one location (or Nationwide) is required")
    return tuple(names)


def validate_record(raw: Mapping[str, object]) -> tuple[Incident | None, list[str]]:
    """Validate and normalise one raw row. Returns (incident, []) or (None, problems)."""
    problems: list[str] = []

    incident_id = _text(raw.get("id"))
    if not _ID.match(incident_id):
        problems.append("id: use 3-40 letters, digits or . _ : -")

    reported = date.min
    try:
        reported = date.fromisoformat(_text(raw.get("reported_date")))
        if not _MIN_DATE <= reported <= date.today() + timedelta(days=1):
            problems.append("reported_date: outside the supported range")
    except ValueError:
        problems.append("reported_date: expected YYYY-MM-DD")

    category = _choice(raw.get("category"), CATEGORIES, "category", problems)
    sector = _choice(raw.get("sector"), SECTORS, "sector", problems)
    source_type = _choice(raw.get("source_type"), SOURCE_TYPES, "source_type", problems)
    verification = _choice(raw.get("verification"), VERIFICATION, "verification", problems)
    scope = _choice(raw.get("scope"), SCOPE_POINTS, "scope", problems)
    service = _choice(raw.get("service_impact"), SERVICE_POINTS, "service_impact", problems)
    data_impact = _choice(raw.get("data_impact"), DATA_POINTS, "data_impact", problems)
    locations = _locations(raw.get("locations"), problems)

    organisation = _text(raw.get("organisation"))
    title = _text(raw.get("title"))
    summary = _text(raw.get("summary"))
    notes = _text(raw.get("notes"))
    source_name = _text(raw.get("source_name"))
    for value, field, limit in (
        (organisation, "organisation", 100), (title, "title", 140), (summary, "summary", 600),
        (notes, "notes", 400), (source_name, "source_name", 100),
    ):
        _check_text(value, field, limit, problems)
    for value, field in ((title, "title"), (summary, "summary"), (source_name, "source_name")):
        if not value:
            problems.append(f"{field}: required")

    source_url = _text(raw.get("source_url"))
    if (url_problem := check_source_url(source_url)) is not None:
        problems.append(url_problem)

    loss: float | None = None
    if loss_text := _text(raw.get("loss_npr_million")):
        try:
            loss = float(loss_text)
            if loss < 0:
                problems.append("loss_npr_million: must not be negative")
        except ValueError:
            problems.append("loss_npr_million: expected a number")

    flag = _text(raw.get("critical_systems")).casefold()
    if flag not in _TRUE | _FALSE:
        problems.append("critical_systems: expected true or false")

    if problems:
        return None, problems
    return Incident(
        id=incident_id, reported_date=reported, category=category, sector=sector, organisation=organisation,
        title=title, summary=summary, locations=locations, source_name=source_name, source_type=source_type,
        source_url=source_url, verification=verification, scope=scope, service_impact=service,
        data_impact=data_impact, loss_npr_million=loss, critical_systems=flag in _TRUE, notes=notes,
    ), []
