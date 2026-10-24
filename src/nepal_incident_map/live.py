"""Live web search over public news RSS feeds.

Only headline, link and date are read from feeds meant for syndication. Article pages are never fetched, nothing is stored,
and every result is labelled unreviewed and unrated until a maintainer checks it.
"""

from __future__ import annotations

import hashlib
import html
import os
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

from nepal_incident_map import data
from nepal_incident_map.geo import GAZETTEER, NATIONWIDE
from nepal_incident_map.schema import validate_record

DISABLE_ENV_VAR = "INCIDENT_LIVE_DISABLED"
LOOKBACK_DAYS = (30, 90, 365)
QUERIES = (
    "Nepal cyber attack", "Nepal ransomware", "Nepal data breach leak", "Nepal website hacked defaced",
    "Nepal phishing scam online fraud", "Nepal DDoS outage cyber",
)


@dataclass(frozen=True)
class Feed:
    label: str
    url: str
    nepali: bool  # a Nepali outlet, so a headline needs no explicit Nepal mention


PUBLISHER_FEEDS = (
    Feed("The Kathmandu Post", "https://kathmandupost.com/rss", True),
    Feed("Onlinekhabar English", "https://english.onlinekhabar.com/feed", True),
    Feed("TechPana", "https://techpana.com/feed", True),
    Feed("ICT Frame", "https://ictframe.com/feed/", True),
)
LOCAL_PUBLISHERS = (
    "kathmandu post", "republica", "onlinekhabar", "khabarhub", "techpana", "ict frame", "himalayan times", "nepali times",
    "setopati", "ratopati", "annapurna express", "nepal live today", "rising nepal", "nepal news",
)

_CYBER = re.compile(
    r"ransomware|cyber|hack(?:ed|er|ers|ing)?\b|data (?:breach|leak)|security breach|phishing|ddos|defac(?:e|ed|ement)|malware|"
    r"dark ?web|online (?:fraud|scam)|scam|spyware|leaked|taken offline|website down|server down", re.I)
_NEPAL = re.compile(
    r"nepal|kathmandu|nepse|\bnrb\b|rastra bank|pokhara|biratnagar|lalitpur|bhaktapur|butwal|nepalgunj|birgunj|janakpur|"
    r"dhangadhi|\bncell\b|\bntc\b|esewa|fonepay|khalti|imepay|nic asia|sebon|cdsc", re.I)
_NOISE = re.compile(
    r"workshop|training|seminar|conference|awareness|policy|strategy|\bbill\b|opinion|editorial|webinar|summit|\bmou\b|agreement|"
    r"launch|inaugurat|competition|\bctf\b|hackathon|course|scholarship|how to|tips\b|"
    r"\burges?\b|\bdirects?\b|\bplans?\b|moves to|establish|trafficking|lessons|everything you need|challenges|may rise|rise sharply", re.I)
_CATEGORY_RULES = (
    ("Ransomware", re.compile(r"ransomware", re.I)),
    ("Defacement", re.compile(r"defac|website (?:was )?hacked|websites? hacked|hacked websites?", re.I)),
    ("Service disruption", re.compile(r"ddos|denial[- ]of[- ]service|outage|taken offline|website down|server down|goes? down|shut down", re.I)),
    ("Data exposure", re.compile(r"data (?:breach|leak)|leaked|dark ?web|exposed|credentials?|breach", re.I)),
    ("Phishing", re.compile(r"phishing|smishing|spoof|impersonat|fake (?:email|sms|message|call)|\bscam", re.I)),
    ("Financial fraud", re.compile(r"fraud|stolen|heist|siphon|theft|swindl|embezzl|hacked.*(?:bank|account|money|wallet)", re.I)),
)
_SECTOR_RULES = (
    ("Capital markets", re.compile(r"nepse|stock|broker|cdsc|sebon|share market", re.I)),
    ("Fintech & payments", re.compile(r"esewa|fonepay|khalti|imepay|wallet|payment|f1soft", re.I)),
    ("Banking & finance", re.compile(r"bank|nrb|rastra|swift|atm|insurance|cooperative", re.I)),
    ("Aviation", re.compile(r"airport|aviation|airline|caan|flight", re.I)),
    ("Telecom", re.compile(r"ncell|nepal telecom|\bntc\b|telecom|isp\b|internet service", re.I)),
    ("Energy", re.compile(r"electricity|\bnea\b|hydropower|energy", re.I)),
    ("Health", re.compile(r"hospital|health|clinic", re.I)),
    ("Education", re.compile(r"universit|college|school|exam|\bneb\b|\bsee\b", re.I)),
    ("Media", re.compile(r"newspaper|television|\btv\b|news portal|media", re.I)),
    ("Government", re.compile(r"government|ministry|department|police|municipal|metropolitan|parliament|\bgov\b|official website|passport|national id", re.I)),
)


@dataclass(frozen=True)
class RawItem:
    title: str
    link: str
    published: date
    publisher: str


@dataclass
class ScanResult:
    rows: list[dict[str, str]] = field(default_factory=list)
    fetched_at: str = ""
    feeds_total: int = 0
    feeds_ok: int = 0
    errors: list[str] = field(default_factory=list)
    seen: int = 0
    matched: int = 0
    unclassified: int = 0
    rejected: int = 0
    duplicates: int = 0


def enabled() -> bool:
    return os.environ.get(DISABLE_ENV_VAR, "").strip().lower() not in {"1", "true", "yes"}


def feeds_for(days: int) -> list[Feed]:
    google = [
        Feed(f"Google News search: {q}", "https://news.google.com/rss/search?q=" + quote_plus(f"{q} when:{days}d", safe=":")
             + "&hl=en-NP&gl=NP&ceid=NP:en", False)
        for q in QUERIES
    ]
    return [*google, *PUBLISHER_FEEDS]


def _item_date(pub_date: str | None, link: str) -> date | None:
    """Publication date from pubDate, or from a /YYYY/MM/DD/ segment in the link when the feed omits it."""
    try:
        return parsedate_to_datetime((pub_date or "").strip()).astimezone(timezone.utc).date()
    except (TypeError, ValueError):
        match = re.search(r"/(20\d\d)/(\d\d)/(\d\d)/", link)
        try:
            return date(*map(int, match.groups())) if match else None
        except ValueError:
            return None


def parse_rss(payload: bytes) -> list[RawItem]:
    """Read RSS 2.0 items. Documents that declare a DTD or entities are refused to rule out entity-expansion attacks."""
    head = payload[:4096].upper()
    if b"<!DOCTYPE" in head or b"<!ENTITY" in payload.upper():
        raise ValueError("feed declares a DTD or entities")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise ValueError("feed is not valid XML") from exc
    items = []
    for node in root.iter("item"):
        title = html.unescape(re.sub(r"<[^>]+>", " ", node.findtext("title") or ""))
        link = (node.findtext("link") or "").strip()
        published = _item_date(node.findtext("pubDate"), link)
        if published is None:
            continue
        publisher = " ".join((node.findtext("source") or "").split())
        title = " ".join(title.split())
        if publisher and title.endswith(f" - {publisher}"):
            title = title[: -len(publisher) - 3].rstrip()
        if title and link:
            items.append(RawItem(title, link, published, publisher))
    return items


def _first(rules, text: str, default: str) -> str:
    return next((name for name, pattern in rules if pattern.search(text)), default)


def classify(title: str) -> tuple[str, str, tuple[str, ...]] | None:
    """Return (category, sector, locations) for a headline, or None when it is not a recognisable incident report."""
    if not _CYBER.search(title) or _NOISE.search(title):
        return None
    category = _first(_CATEGORY_RULES, title, "")
    if not category:
        return None
    places = tuple(name for name in GAZETTEER if re.search(rf"\b{re.escape(name)}\b", title, re.I)) or (NATIONWIDE,)
    return category, _first(_SECTOR_RULES, title, "Other"), places


def _relevant(item: RawItem, feed: Feed) -> bool:
    if feed.nepali:
        return True
    return bool(_NEPAL.search(item.title)) or any(name in item.publisher.lower() for name in LOCAL_PUBLISHERS)


def to_row(item: RawItem, feed: Feed) -> dict[str, str] | None:
    found = classify(item.title)
    if found is None:
        return None
    category, sector, places = found
    publisher = item.publisher or feed.label.split(": ")[0]
    return {
        "id": "W-" + hashlib.sha1(item.link.encode()).hexdigest()[:10], "reported_date": item.published.isoformat(),
        "category": category, "sector": sector, "organisation": "", "title": item.title[:140],
        "summary": f"Headline from {publisher}, matched automatically as {category.lower()}. Not reviewed: open the source for the facts.",
        "locations": ";".join(places), "source_name": publisher[:100], "source_type": "News media", "source_url": item.link,
        "verification": "Reported", "scope": "Single organisation", "service_impact": "None", "data_impact": "None",
        "loss_npr_million": "", "critical_systems": "false", "assessed": "false",
        "notes": "Auto-detected from a public RSS feed. Unreviewed and unrated.",
    }


def _norm(title: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", title.lower())


def _similar(a: str, b: str) -> bool:
    return SequenceMatcher(None, a, b).ratio() >= 0.8


def drop_known(rows: list[dict[str, str]], known_titles: list[str], known_urls: set[str]) -> tuple[list[dict[str, str]], int]:
    """Remove results that repeat an incident already in the curated data."""
    known = [_norm(t) for t in known_titles]
    kept = [r for r in rows if r["source_url"] not in known_urls and not any(_similar(_norm(r["title"]), k) for k in known)]
    return kept, len(rows) - len(kept)


def scan(days: int, fetch=data.fetch_feed) -> ScanResult:
    """Read every feed in parallel and return validated, de-duplicated candidate rows, newest first."""
    feeds = feeds_for(days)
    result = ScanResult(fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"), feeds_total=len(feeds))

    def read(feed: Feed):
        try:
            return feed, parse_rss(fetch(feed.url)), ""
        except ValueError as exc:
            return feed, [], str(exc)

    with ThreadPoolExecutor(max_workers=6) as pool:
        outcomes = list(pool.map(read, feeds))
    oldest, newest = date.today() - timedelta(days=days), date.today() + timedelta(days=1)
    candidates: list[dict[str, str]] = []
    for feed, items, error in outcomes:
        if error:
            result.errors.append(f"{feed.label}: {error}")
            continue
        result.feeds_ok += 1
        for item in items:
            result.seen += 1
            if not oldest <= item.published <= newest or not _relevant(item, feed):
                continue
            if (row := to_row(item, feed)) is not None:
                candidates.append(row)
            elif _CYBER.search(item.title):
                result.unclassified += 1
    kept: list[dict[str, str]] = []
    for row in sorted(candidates, key=lambda r: r["reported_date"]):
        incident, _ = validate_record(row)
        if incident is None:
            result.rejected += 1
        elif any(row["id"] == k["id"] or _similar(_norm(row["title"]), _norm(k["title"])) for k in kept):
            result.duplicates += 1
        else:
            kept.append(row)
    result.matched = len(kept)
    result.rows = sorted(kept, key=lambda r: r["reported_date"], reverse=True)[:150]
    return result
