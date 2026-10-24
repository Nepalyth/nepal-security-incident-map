"""Hand-built SVG/HTML visuals: Himalayan skyline, Nepal flag, radar-style incident map and story timeline.

Every string that comes from a record is escaped. Output is one line per block so Markdown never reinterprets it.
"""

from __future__ import annotations

import html
import math
import random

import pandas as pd

from nepal_incident_map import data
from nepal_incident_map.geo import GAZETTEER
from nepal_incident_map.schema import severity_of
from nepal_incident_map.theme import CATEGORY_COLORS, CYAN, SEVERITY_COLORS, STATUS_COLORS, chip

esc = html.escape

# (x, summit y, name, height) laid out west to east across a 1440 x 300 canvas.
PEAKS = [
    (300, 96, "Dhaulagiri", "8,167 m"), (440, 108, "Annapurna I", "8,091 m"), (580, 98, "Manaslu", "8,163 m"),
    (790, 46, "Sagarmatha", "8,849 m"), (960, 78, "Makalu", "8,485 m"), (1130, 64, "Kanchenjunga", "8,586 m"),
]
NAV = (("globe", "Globe"), ("map", "Map"), ("story", "Timeline"), ("trends", "Trends"), ("log", "Incident log"), ("how", "Method"))


def _star(cx: float, cy: float, points: int, outer: float, inner: float) -> str:
    coords = []
    for i in range(points * 2):
        radius = outer if i % 2 == 0 else inner
        angle = math.radians(-90 + i * 180 / points)
        coords.append(f"{cx + radius * math.cos(angle):.2f},{cy + radius * math.sin(angle):.2f}")
    return " ".join(coords)


def flag_svg(height: int = 64, uid: str = "f") -> str:
    """Flag of Nepal: two stacked pennants, crimson field, blue border, white moon (upper) and sun (lower)."""
    return (
        f"<svg class='flag' viewBox='-6 -6 94 112' height='{height}' xmlns='http://www.w3.org/2000/svg' role='img' aria-label='Flag of Nepal'>"
        f"<defs><mask id='{uid}m'><rect x='-10' y='-10' width='120' height='130' fill='#fff'/><circle cx='20' cy='29.2' r='9.8' fill='#000'/></mask></defs>"
        "<polygon points='0,0 62,43 24,43 82,100 0,100' fill='#dc143c' stroke='#003893' stroke-width='10' stroke-miterlimit='10' paint-order='stroke fill'/>"
        f"<circle cx='20' cy='33' r='11.5' fill='#fff' mask='url(#{uid}m)'/>"
        f"<polygon points='{_star(20, 30.5, 8, 4.6, 2.1)}' fill='#fff'/>"
        f"<circle cx='19' cy='72' r='6' fill='#fff'/><polygon points='{_star(19, 72, 12, 13, 8)}' fill='#fff'/></svg>"
    )


def _ridge(rng: random.Random, base: float, peaks: list[tuple[float, float]], spread: float, jitter: float) -> list[tuple[float, float]]:
    points = []
    for x in range(-20, 1461, 10):
        lift = max((base - py) * max(0.0, 1 - abs(x - px) / spread) for px, py in peaks)
        near_peak = any(abs(x - px) < 40 for px, _ in peaks)
        points.append((x, base - lift + (0 if near_peak else rng.uniform(-jitter, jitter))))
    return points


def _path(points: list[tuple[float, float]], floor: float = 300) -> str:
    return "M" + " L".join(f"{x:.0f},{y:.1f}" for x, y in points) + f" L1460,{floor} L-20,{floor} Z"


def mountains_svg() -> str:
    rng = random.Random(11)
    far = _ridge(rng, 205, [(x, y + 40) for x, y, _, _ in PEAKS], 170, 7)
    mid_peaks = [(rng.uniform(0, 1440), rng.uniform(190, 225)) for _ in range(9)]
    mid = _ridge(rng, 262, mid_peaks, 160, 5)
    near = _ridge(rng, 292, [(rng.uniform(0, 1440), rng.uniform(268, 284)) for _ in range(8)], 140, 3)
    snow, labels = [], []
    for x, y, name, height in PEAKS:
        y += 40
        slope = (205 - y) / 170
        depth = 34
        half = depth / slope
        zig = f"{x - half:.0f},{y + depth} {x - half * 0.55:.0f},{y + depth * 0.62} {x - half * 0.2:.0f},{y + depth * 0.95} {x + half * 0.2:.0f},{y + depth * 0.7} {x + half * 0.6:.0f},{y + depth * 0.98}"
        snow.append(f"<polygon class='snow' points='{x},{y} {zig} {x + half:.0f},{y + depth}' fill='#eaf8ff' opacity='.88'/>")
        labels.append(
            f"<g class='peak'><line x1='{x}' y1='{y - 6}' x2='{x}' y2='{y - 26}' stroke='#00e5ff' stroke-opacity='.5'/>"
            f"<text x='{x}' y='{y - 44}' text-anchor='middle' class='pk-n'>{esc(name)}</text>"
            f"<text x='{x}' y='{y - 31}' text-anchor='middle' class='pk-h'>{esc(height)}</text></g>"
        )
    stars = "".join(
        f"<circle cx='{rng.uniform(0, 1440):.0f}' cy='{rng.uniform(4, 120):.0f}' r='{rng.uniform(.5, 1.5):.1f}' fill='#cfeaff' "
        f"class='{'tw' if i % 4 == 0 else ''}' opacity='{rng.uniform(.25, .8):.2f}'/>" for i in range(80)
    )
    return (
        "<svg class='peaks' viewBox='0 0 1440 300' preserveAspectRatio='xMidYMax slice' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>"
        "<defs><linearGradient id='mfar' x1='0' y1='0' x2='0' y2='1'><stop class='mf0' offset='0' stop-color='#2a5a9c'/><stop class='mf1' offset='1' stop-color='#0e1d3d'/></linearGradient>"
        "<linearGradient id='mmid' x1='0' y1='0' x2='0' y2='1'><stop class='mm0' offset='0' stop-color='#14284d'/><stop class='mm1' offset='1' stop-color='#09132a'/></linearGradient></defs>"
        f"<g class='stars'>{stars}</g><path class='mt-far' d='{_path(far)}' fill='url(#mfar)' stroke='#00e5ff' stroke-opacity='.45' stroke-width='1.2'/>{''.join(snow)}"
        f"<path class='mt-mid' d='{_path(mid)}' fill='url(#mmid)' stroke='#00e5ff' stroke-opacity='.18'/>"
        f"<path class='mt-near' d='{_path(near)}' fill='#060c1b'/>{''.join(labels)}</svg>"
    )


def _ticker_item(row) -> str:
    return (
        f"<span class='tk' style='--c:{SEVERITY_COLORS[row.severity]}'><b>{esc(row.severity.upper())}</b> {row.date:%d %b %Y} "
        f"<i>/</i> {esc(row.category)} <i>/</i> {esc(row.title)}</span>"
    )


def hero_html(frame: pd.DataFrame, total: int) -> str:
    latest = frame["date"].max()
    recent = int((frame["date"] > pd.Timestamp.today().normalize() - pd.Timedelta(days=90)).sum())
    ticker = "".join(_ticker_item(r) for r in frame.head(8).itertuples())
    chips = " ".join([
        "<span class='chip' style='--c:#2de6a6'><span class='live'></span>" + f"{total} records loaded</span>",
        chip(f"Latest report {latest:%d %b %Y}", CYAN),
        chip(f"{recent} reports in the last 90 days", "#ff7a3d"),
        chip("City-level only"), chip("Sources on every record"),
    ])
    return (
        "<section class='hero2' id='top'><div class='aurora'></div>" + mountains_svg()
        + "<div class='hero2-in'><div class='hero2-flag'>" + flag_svg(132, "h") + "</div><div class='hero2-text'>"
        "<div class='eyebrow'>Nepal &middot; public cyber incident observatory</div>"
        "<h1 class='glitch' data-t='NEPAL CYBER INCIDENT MAP'>NEPAL CYBER INCIDENT MAP</h1>"
        "<div class='np'>नेपाल साइबर घटना नक्सा</div>"
        "<p>Where, when and how digital attacks hit Nepal, built only from public reporting, official disclosures and authorised feeds. "
        "No private data, no unverified accusations, nothing an attacker could use.</p>"
        f"<div class='ribbon'>{chips}</div></div></div>"
        f"<div class='ticker'><span class='tk-tag'>SIGNAL FEED</span><div class='tk-wrap'><div class='tk-track'>{ticker}{ticker}</div></div></div>"
        "<div class='dhaka'></div></section>"
    )


def nav_html() -> str:
    links = "".join(f"<a href='#{anchor}'>{label}</a>" for anchor, label in NAV)
    return (
        f"<nav class='nav'><a class='nav-brand' href='#top'>{flag_svg(30, 'n')}<b>NEPAL CYBER MAP</b></a>"
        f"<div class='nav-links'>{links}</div><span class='chip' style='--c:#2de6a6'><span class='live'></span>LIVE DATA</span></nav>"
    )


def section_head(anchor: str, number: str, title: str, hint: str) -> str:
    return (
        f"<div class='sec' id='{anchor}'><div><div class='n'>// {number}</div><h2>{esc(title)}</h2></div>"
        f"<p>{esc(hint)}</p></div>"
    )


def _tip_items(lines: list[str], limit: int = 5) -> str:
    items = "".join(f"<li>{esc(line)}</li>" for line in lines[:limit])
    more = f"<li class='more'>+{len(lines) - limit} more</li>" if len(lines) > limit else ""
    return f"<ul>{items}{more}</ul>"


def map_html(frame: pd.DataFrame) -> str:
    """Offline radar-style map: province outlines, pulsing severity pins, hover cards, no tiles or WebGL."""
    lon0, lat1, scale, ystretch = 80.0, 30.5, 100.0, 1.13
    width, height = 830, 475

    def project(lon: float, lat: float) -> tuple[float, float]:
        return (lon - lon0) * scale, (lat1 - lat) * scale * ystretch

    places = data.location_summary(frame)
    per_province = places.groupby("province")["count"].sum() if len(places) else pd.Series(dtype=int)
    peak = max(int(per_province.max()), 1) if len(per_province) else 1

    grid = "".join(f"<line class='grat' x1='{(lon - lon0) * scale}' y1='0' x2='{(lon - lon0) * scale}' y2='{height}'/>" for lon in range(81, 89))
    grid += "".join(f"<line class='grat' x1='0' y1='{(lat1 - lat) * scale * ystretch:.0f}' x2='{width}' y2='{(lat1 - lat) * scale * ystretch:.0f}'/>" for lat in range(27, 31))
    provinces, labels = [], []
    for name, rings in data.load_provinces().items():
        reports = int(per_province.get(name, 0))
        fill = f"rgba(0,229,255,{0.05 + 0.30 * reports / peak:.3f})"
        for ring in rings:
            d = "M" + " L".join("{:.1f},{:.1f}".format(*project(lon, lat)) for lon, lat in ring) + " Z"
            provinces.append(f"<path class='prov' d='{d}' style='fill:{fill}'><title>{esc(name)}: {reports} city-level report(s)</title></path>")
        xs, ys = zip(*(project(lon, lat) for lon, lat in max(rings, key=len)))
        labels.append(f"<text class='plab' x='{sum(xs) / len(xs):.0f}' y='{sum(ys) / len(ys) + 34:.0f}'>{esc(name.upper())}</text>")

    ox, oy = project(GAZETTEER["Kathmandu"][1], GAZETTEER["Kathmandu"][0])
    radius = 520
    tip_x, tip_y = ox + radius * math.cos(math.radians(-38)), oy + radius * math.sin(math.radians(-38))
    rings_svg = "".join(f"<circle class='ringr' cx='{ox:.0f}' cy='{oy:.0f}' r='{r}'/>" for r in (90, 180, 270, 360))
    sweep = (
        f"<g class='sweep' style='transform-origin:{ox:.0f}px {oy:.0f}px'><path d='M{ox:.0f},{oy:.0f} L{ox + radius:.0f},{oy:.0f} "
        f"A{radius},{radius} 0 0 0 {tip_x:.0f},{tip_y:.0f} Z' fill='url(#sweepg)'/>"
        f"<line x1='{ox:.0f}' y1='{oy:.0f}' x2='{ox + radius:.0f}' y2='{oy:.0f}' stroke='#00e5ff' stroke-opacity='.55'/></g>"
    )
    svg = (
        f"<svg class='mapsvg' viewBox='0 0 {width} {height}' xmlns='http://www.w3.org/2000/svg' aria-hidden='true'>"
        f"<defs><radialGradient id='sweepg' gradientUnits='userSpaceOnUse' cx='{ox:.0f}' cy='{oy:.0f}' r='{radius}'>"
        "<stop offset='0' stop-color='#00e5ff' stop-opacity='.26'/><stop offset='1' stop-color='#00e5ff' stop-opacity='0'/></radialGradient></defs>"
        f"{grid}{rings_svg}{''.join(provinces)}{''.join(labels)}{sweep}</svg>"
    )

    def pin(left: float, top: float, name: str, sub: str, count: int, severity: str, lines: list[str], extra: str = "") -> str:
        size = 12 + 5 * math.sqrt(count)
        pulse = {"Critical": 1.6, "High": 2.2, "Medium": 3.0, "Low": 4.0, "Unrated": 4.5}[severity]
        side = " right" if left > 68 else (" left" if left < 22 else "")
        return (
            f"<div class='pin{side}{extra}' tabindex='0' style='left:{left:.2f}%;top:{top:.2f}%;--c:{SEVERITY_COLORS[severity]};--s:{size:.0f}px;--d:{pulse}s'>"
            "<span class='ring'></span><span class='ring r2'></span><span class='core'></span>"
            f"<span class='lbl'>{esc(name)}</span><div class='tip'><div class='tip-h'><b>{esc(name)}</b><em>{esc(sub)}</em>"
            f"<span>{count} incident{'s' if count != 1 else ''}</span></div>{_tip_items(lines)}</div></div>"
        )

    pins = []
    for row in places.itertuples():
        x, y = project(GAZETTEER[row.location][1], GAZETTEER[row.location][0])
        pins.append(pin(x / width * 100, y / height * 100, row.location, row.province, row.count, row.severity, row.lines))
    unplaced = frame[pd.Series([not any(loc in GAZETTEER for loc in locs) for locs in frame["locations"]], index=frame.index, dtype=bool)]
    if len(unplaced):
        lines = [f"{r.date:%d %b %Y} | {r.category} | {r.severity}: {r.title}" for r in unplaced.itertuples()]
        worst = max(unplaced["score"])
        pins.append(pin(7, 86, "Nationwide", "no single city", len(unplaced), severity_of(worst), lines, " nw"))

    legend = "".join(chip(s, c) for s, c in SEVERITY_COLORS.items())
    plotted = int(places["count"].sum()) if len(places) else 0
    return (
        "<div class='mapwrap'><div class='hud tl'>NEPAL // INCIDENT RADAR</div><div class='hud tr'>SCAN ACTIVE &middot; 27.7&deg;N 85.3&deg;E</div>"
        f"<div class='mapbox'><i class='cn a'></i><i class='cn b'></i><i class='cn c'></i><i class='cn d'></i>{svg}{''.join(pins)}</div>"
        f"<div class='maplegend'>{legend}<span class='note'>pulse = incident, colour = worst severity, size = number of incidents. "
        f"Hover or tap a pin for details. {plotted} city-level report(s) plotted.</span></div></div>"
    )


def feed_html(frame: pd.DataFrame, limit: int = 12) -> str:
    out = []
    for r in frame.head(limit).itertuples():
        bs = data.bs_label(r.date)
        out.append(
            f"<div class='feed-item' style='--c:{SEVERITY_COLORS[r.severity]}'><div class='t'>{esc(r.title)}</div>"
            f"<div class='m'>{r.date:%d %b %Y}{f' | BS {esc(bs)}' if bs else ''} | {esc(' / '.join(r.locations))}</div>{chips_html(r)}</div>"
        )
    return "".join(out)


def chips_html(row) -> str:
    live = [chip("LIVE WEB / UNREVIEWED", "#ffb020")] if row.origin == "web" else []
    return " ".join([
        *live, chip(row.severity, SEVERITY_COLORS[row.severity]), chip(row.category, CATEGORY_COLORS[row.category]),
        chip(row.verification, STATUS_COLORS[row.verification]), chip(row.sector),
    ])


def timeline_html(frame: pd.DataFrame) -> str:
    """Alternating vertical timeline grouped by year, newest first."""
    out, index = ["<div class='tl'>"], 0
    for year, group in frame.groupby("year", sort=False):
        out.append(f"<div class='tl-year'><span>{year}</span><em>{len(group)} report{'s' if len(group) != 1 else ''}</em></div>")
        for r in group.itertuples():
            bs = data.bs_label(r.date)
            org = f"{esc(r.organisation)} &middot; " if r.organisation else ""
            out.append(
                f"<article class='tl-item {'l' if index % 2 == 0 else 'r'}' style='--c:{SEVERITY_COLORS[r.severity]}'><span class='tl-dot'></span>"
                f"<div class='tl-card'><div class='tl-date'>{r.date:%d %b %Y}{f' &middot; BS {esc(bs)}' if bs else ''}</div>"
                f"<h4>{esc(r.title)}</h4><div class='tl-chips'>{chips_html(r)}</div><p>{esc(r.summary)}</p>"
                f"<div class='tl-foot'>{org}{esc(' / '.join(r.locations))} &middot; "
                f"<a href='{esc(r.source_url)}' target='_blank' rel='noopener noreferrer'>{esc(r.source_name)}</a></div></div></article>"
            )
            index += 1
    out.append("</div>")
    return "".join(out)
