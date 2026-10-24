"""Streamlit UI: one scrolling page with a map, story timeline and trends of publicly reported cyber incidents in Nepal."""

from __future__ import annotations

import csv
import html
import time
from datetime import date, datetime

import pandas as pd
import streamlit as st

from nepal_incident_map import charts, data, globe, live, theme, visuals
from nepal_incident_map.geo import GAZETTEER, NATIONWIDE
from nepal_incident_map.schema import (
    CATEGORIES, DATA_POINTS, SCOPE_POINTS, SECTORS, SERVICE_POINTS, SEVERITIES, SOURCE_TYPES, VERIFICATION,
    VERIFICATION_HELP, score_parts,
)
from nepal_incident_map.theme import SEVERITY_COLORS, STATUS_COLORS

st.set_page_config(page_title="Nepal Cyber Incident Map", page_icon="🛡️", layout="wide", initial_sidebar_state="collapsed")
if "light_mode" not in st.session_state:
    st.session_state["light_mode"] = st.query_params.get("theme") == "light"
light = bool(st.session_state["light_mode"])
theme.inject(light)
pal = theme.palette(light)

PLOT = {"width": "stretch", "config": {"displayModeBar": False}}
esc = html.escape


def _html(block: str) -> None:
    """Render a single-line HTML block; st.markdown keeps inline SVG, which st.html strips."""
    st.markdown(block, unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def _seed_rows() -> list[dict[str, str]]:
    return data.load_seed_rows()


@st.cache_data(show_spinner=False)
def _local_rows(version: float) -> list[dict[str, str]]:
    return data.read_local_rows()


@st.cache_data(ttl=data.feed_ttl_seconds(), show_spinner=False)
def _remote_rows(url: str) -> tuple[list[dict[str, object]], str]:
    try:
        return data.parse_feed(data.fetch_feed(url), url.split("?")[0]), ""
    except (ValueError, csv.Error) as exc:
        return [], str(exc)


@st.cache_data(ttl=900, max_entries=6, show_spinner=False)
def _scan(days: int, bucket: int) -> live.ScanResult:
    """One network scan per look-back window every five minutes, shared by all sessions to go easy on the feeds."""
    return live.scan(days)


@st.fragment(run_every=300)
def _auto_scan(days: int) -> None:
    """Re-check the feeds every five minutes and redraw the whole page only when the headlines changed."""
    fresh, old = _scan(days, int(time.time() // 300)), st.session_state.get("scan")
    if old is None or [r["id"] for r in fresh.rows] != [r["id"] for r in old.rows]:
        st.session_state["scan"] = fresh
        st.rerun()
    st.caption(f"Auto-refresh on. Last check {datetime.now():%H:%M}; the next in about 5 minutes.")


def _csv_safe(value: object) -> object:
    """Neutralise spreadsheet formulas in exported text cells."""
    return "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@")) else value


# ---------------------------------------------------------------- data (uploader lives in the Method section)
rows: list[tuple[str, dict]] = [("bundled", r) for r in _seed_rows()]
rows += [("local", r) for r in _local_rows(data.local_store_version())]
feed_errors: list[str] = []
for url in data.configured_feed_urls():
    remote, error = _remote_rows(url)
    feed_errors += [error] if error else []
    rows += [("feed", r) for r in remote]
for upload in st.session_state.get("feed_upload") or []:
    try:
        rows += [(f"upload: {upload.name[:40]}", r) for r in data.parse_feed(upload.getvalue(), upload.name)]
    except (ValueError, csv.Error) as exc:
        feed_errors.append(f"{upload.name[:40]}: {exc}")

mode = st.session_state.get("source_mode") or "Curated CSV"
scan: live.ScanResult | None = st.session_state.get("scan") if live.enabled() else None
known_dupes = 0
if scan and mode != "Curated CSV":
    fresh, known_dupes = live.drop_known(
        scan.rows, [str(r.get("title", "")) for _, r in rows], {str(r.get("source_url", "")) for _, r in rows},
    )
    live_rows = [("web", r) for r in fresh]
    rows = live_rows if mode == "Live web search" and live_rows else rows + live_rows

result = data.build_frame(rows)
everything = result.incidents
if everything.empty:
    st.error("No valid incident records could be loaded.")
    st.stop()
first_day, last_day = everything["date"].min().date(), everything["date"].max().date()
sev_options = [s for s in SEVERITIES if s != "Unrated" or (everything["severity"] == "Unrated").any()]

# ---------------------------------------------------------------- nav, hero, filters
_html(visuals.nav_html())
with st.container(key="themebox"):
    st.toggle("Light mode", key="light_mode")
if st.query_params.get("theme") != ("light" if light else "dark"):
    st.query_params["theme"] = "light" if light else "dark"
_html(visuals.hero_html(everything, len(everything)))
for message in feed_errors:
    st.warning(f"Feed skipped: {message}")

with st.container(border=True):
    st.markdown('<div class="ptitle">Data and filters <span class="note">&nbsp;every section below follows these</span></div>', unsafe_allow_html=True)
    if live.enabled():
        chosen_mode = st.segmented_control(
            "Data source", ["Curated CSV", "Live web search", "Both"], default="Curated CSV", key="source_mode",
            help="Curated CSV is the reviewed dataset. Live web search reads public news RSS feeds for new headlines (unreviewed). Both shows them together.",
        ) or "Curated CSV"
        if chosen_mode != "Curated CSV":
            k1, k2, k3 = st.columns([1, 1.2, 3], gap="medium")
            days = k1.selectbox("Look back", live.LOOKBACK_DAYS, index=1, key="live_days", format_func=lambda d: f"{d} days" if d < 365 else "1 year")
            first_scan = st.session_state.get("scan") is None
            k2.markdown('<div style="height:1.65rem"></div>', unsafe_allow_html=True)
            if k2.button("Scan the live web now", key="scan_btn") or first_scan:
                with st.spinner("Reading public news feeds..."):
                    st.session_state["scan"] = _scan(days, int(time.time() // 300))
                st.rerun()
            if scan:
                when = datetime.fromisoformat(scan.fetched_at).astimezone().strftime("%d %b %H:%M")
                k3.markdown(
                    f'<p class="note">Last scan {when}: {scan.feeds_ok} of {scan.feeds_total} feeds read, {scan.seen} headlines checked, '
                    f'<b>{scan.matched}</b> look like Nepal cyber incidents, {known_dupes} already in the curated data.</p>', unsafe_allow_html=True)
                if scan.errors:
                    with k3.expander(f"{len(scan.errors)} feed(s) could not be read"):
                        st.write("\n".join(f"- {esc(e)}" for e in scan.errors))
            with k3:
                if st.toggle("Auto-refresh every 5 minutes", key="auto_scan", help="Re-checks the feeds in the background and redraws the page when a new headline appears."):
                    _auto_scan(days)
    c1, c2 = st.columns([1, 1.4], gap="large")
    span = c1.date_input("Reported between", value=(first_day, last_day), min_value=first_day, max_value=last_day)
    query = c2.text_input("Search", placeholder="bank, ransomware, airport...")
    severities = st.pills("Severity", sev_options, selection_mode="multi", default=sev_options)
    statuses = st.pills(
        "Verification", VERIFICATION, selection_mode="multi", default=["Confirmed", "Reported"],
        help="\n\n".join(f"**{k}**: {v}" for k, v in VERIFICATION_HELP.items()),
    )
    categories = st.pills("Category", CATEGORIES, selection_mode="multi", default=list(CATEGORIES))
    all_sectors = sorted(everything["sector"].unique())
    sectors = st.pills("Sector", all_sectors, selection_mode="multi", default=all_sectors)

start, end = span if isinstance(span, tuple) and len(span) == 2 else (first_day, last_day)
mask = (
    everything["date"].between(pd.Timestamp(start), pd.Timestamp(end))
    & everything["category"].isin(categories or []) & everything["sector"].isin(sectors or [])
    & everything["severity"].isin(severities or []) & everything["verification"].isin(statuses or [])
)
if query.strip():
    needle = query.strip().casefold()
    mask &= everything["title"].str.casefold().str.contains(needle, regex=False) | everything["summary"].str.casefold().str.contains(needle, regex=False)
df = everything[mask]

if df.empty:
    st.info("No incidents match the current filters. Widen the date range or select more options.")
    st.stop()

# ---------------------------------------------------------------- KPIs
today = pd.Timestamp.today().normalize()
read = charts.insights(df)
if (n_live := int((df["origin"] == "web").sum())):
    _html(
        f'<div class="callout"><b>{n_live} live web result(s) in view.</b> These are headlines from public news feeds, sorted into categories by keywords. '
        "They are unreviewed and unrated, so open the source before relying on one. The curated CSV stays the reviewed record.</div>"
    )
recent = int((df["date"] > today - pd.DateOffset(months=12)).sum())
previous = int(((df["date"] <= today - pd.DateOffset(months=12)) & (df["date"] > today - pd.DateOffset(months=24))).sum())
serious = int(df["severity"].isin(["High", "Critical"]).sum())
top_sector = df["sector"].value_counts()
_html(
    '<div class="kpis">'
    + theme.kpi("Incidents in view", str(len(df)), f"{df['date'].min():%b %Y} to {df['date'].max():%b %Y}")
    + theme.kpi("Last 12 months", str(recent), f"{recent - previous:+d} vs the 12 months before", theme.CRIMSON)
    + theme.kpi("High or critical", str(serious), f"{(df['severity'] == 'Critical').sum()} critical", SEVERITY_COLORS["High"])
    + theme.kpi("Confirmed", f"{(df['verification'] == 'Confirmed').mean():.0%}", "acknowledged by victim or authority", STATUS_COLORS["Confirmed"])
    + theme.kpi("Most-hit sector", top_sector.index[0], f"{top_sector.iloc[0]} reported incident(s)", "#b57bff")
    + "</div>"
)

# ---------------------------------------------------------------- 01 globe
_html(visuals.section_head("globe", "01", "Cyber globe", "Drag the globe to rotate it. Each pulsing beacon is a place with reported incidents; amber dashed rings are unreviewed live web headlines."))
with st.container(border=True):
    st.iframe(globe.globe_src(df, light), height=580)
    st.markdown(
        '<p class="note">Unlike a sensor network such as Kaspersky Cybermap, this globe shows <b>reported incidents</b>, not live traffic. '
        "It draws no attack arcs because public reports rarely say where an attack came from, and guessing would be an unverified accusation. "
        "Real-time telemetry needs a data provider; feed it in through an authorised feed and it will show up here.</p>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------- 02 map
_html(visuals.section_head("map", "02", "Incident radar", "Each pulse is a city with reported incidents. Hover or tap a pin to read what was reported there."))
map_col, feed_col = st.columns([5, 2], gap="medium")
with map_col, st.container(border=True):
    _html(visuals.map_html(df))
    st.markdown(
        '<p class="note">Locations are city-level only; incidents with no single city sit under the Nationwide pin. '
        "Province shading counts city-level reports. Outlines: geoBoundaries (CC BY 3.0 IGO; Survey Department of Nepal, OCHA).</p>",
        unsafe_allow_html=True,
    )
with feed_col, st.container(border=True, height=600):
    st.markdown('<div class="ptitle">Latest reports</div>', unsafe_allow_html=True)
    _html(visuals.feed_html(df))

# ---------------------------------------------------------------- 02 timeline
_html(visuals.section_head("story", "03", "Timeline", "The chart shows every report by year and severity. The story below reads newest first, one card per report."))
with st.container(border=True):
    st.markdown('<div class="ptitle">Overview: every report by year and severity</div>', unsafe_allow_html=True)
    st.caption("Each stem is one report. Height shows its severity band, colour shows the category, and the shape shows verification (circle = confirmed, diamond = reported, open = claimed). Labels name the High and Critical incidents; hover any marker for details.")
    st.plotly_chart(charts.timeline_figure(df, pal), **PLOT)
_html(visuals.timeline_html(df))

# ---------------------------------------------------------------- 03 trends
_html(visuals.section_head("trends", "04", "Historical trends", "Counts are of publicly reported incidents, so a rise can mean better disclosure as much as more attacks."))
a, b = st.columns([2, 1], gap="medium")
with a, st.container(border=True):
    st.markdown('<div class="ptitle">Reported incidents per year</div>', unsafe_allow_html=True)
    _html(f'<div class="insight">{read["yearly"]}</div>')
    st.plotly_chart(charts.yearly_stacked(df, pal), **PLOT)
with b, st.container(border=True):
    st.markdown('<div class="ptitle">By category</div>', unsafe_allow_html=True)
    _html(f'<div class="insight">{read["category"]}</div>')
    st.plotly_chart(charts.category_donut(df, pal), **PLOT)
c, d = st.columns(2, gap="medium")
with c, st.container(border=True):
    st.markdown('<div class="ptitle">Sector by year</div>', unsafe_allow_html=True)
    _html(f'<div class="insight">{read["sector"]}</div>')
    st.plotly_chart(charts.sector_heatmap(df, pal), **PLOT)
with d, st.container(border=True):
    st.markdown('<div class="ptitle">Severity by year</div>', unsafe_allow_html=True)
    _html(f'<div class="insight">{read["severity"]}</div>')
    st.plotly_chart(charts.severity_by_year(df, pal), **PLOT)
e, f = st.columns(2, gap="medium")
with e, st.container(border=True):
    st.markdown('<div class="ptitle">Cumulative reports</div>', unsafe_allow_html=True)
    _html(f'<div class="insight">{read["cumulative"]}</div>')
    st.plotly_chart(charts.cumulative_figure(df, pal), **PLOT)
with f, st.container(border=True):
    st.markdown('<div class="ptitle">Official context: Nepal Police Cyber Bureau</div>', unsafe_allow_html=True)
    _html(f'<div class="insight">{read["official"]}</div>')
    st.plotly_chart(charts.official_stats_figure(pal), **PLOT)
    st.markdown(
        '<p class="note">Cases registered by fiscal year. Financial scams and fraud rose by 87.8% (4,112 to 7,723). '
        "The bureau warns totals may be undercounted because district offices also handle cases. "
        f'<a href="{esc(data.CYBER_BUREAU_SOURCE)}" target="_blank" rel="noopener noreferrer">The Kathmandu Post</a>.</p>',
        unsafe_allow_html=True,
    )
g, h = st.columns([1, 2], gap="medium")
with g, st.container(border=True):
    st.markdown('<div class="ptitle">Verification status</div>', unsafe_allow_html=True)
    _html(f'<div class="insight">{read["status"]}</div>')
    st.plotly_chart(charts.status_donut(df, pal), **PLOT)
with h, st.container(border=True):
    st.markdown('<div class="ptitle">How records are verified</div>', unsafe_allow_html=True)
    _html("".join(
        f'<div class="feed-item" style="--c:{STATUS_COLORS[k]}"><div class="t">{k}</div><div class="m">{esc(v)}</div></div>'
        for k, v in VERIFICATION_HELP.items()
    ))

# ---------------------------------------------------------------- 04 log
_html(visuals.section_head("log", "05", "Incident log", "Every record in a table. Download the filtered set, or open one incident to see how its severity was scored."))
with st.container(border=True):
    table = df.assign(data=df["origin"].map(lambda o: "Live web" if o == "web" else o.split(":")[0].capitalize()))[
        ["date", "data", "category", "sector", "organisation", "title", "severity", "verification", "source_name", "source_url"]]
    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "date": st.column_config.DateColumn("Reported", format="DD MMM YYYY"), "data": "Data",
            "category": "Category", "sector": "Sector", "organisation": "Organisation", "title": st.column_config.TextColumn("Incident", width="large"),
            "severity": "Severity", "verification": "Status", "source_name": "Source",
            "source_url": st.column_config.LinkColumn("Link", display_text="open"),
        },
    )
    export = df.drop(columns=["year"]).assign(locations=df["locations"].map("; ".join)).map(_csv_safe)
    st.download_button("Download filtered records (CSV)", export.to_csv(index=False).encode("utf-8"), "nepal-cyber-incidents.csv", "text/csv")

chosen = st.selectbox(
    "Open an incident", df["id"],
    format_func=lambda i: f"{df.loc[df['id'] == i, 'date'].iloc[0]:%d %b %Y}  |  {df.loc[df['id'] == i, 'title'].iloc[0]}",
)
row = next(df[df["id"] == chosen].itertuples())
parts = score_parts(row.scope, row.service_impact, row.data_impact, row.loss_npr_million, row.critical_systems)
info, score = st.columns([3, 2], gap="medium")
with info, st.container(border=True):
    bs = data.bs_label(row.date)
    _html(
        f'<div class="detail"><div class="ptitle">{esc(row.id)}</div><h3>{esc(row.title)}</h3>{visuals.chips_html(row)}'
        f'<p class="summary">{esc(row.summary)}</p>'
        f'<p class="note"><b>Reported</b> {row.date:%d %b %Y}{f" (BS {esc(bs)})" if bs else ""}<br>'
        f'<b>Organisation</b> {esc(row.organisation or "Not named / sector-level")}<br>'
        f'<b>Locations</b> {esc(" / ".join(row.locations))}<br>'
        f'<b>Source</b> <a href="{esc(row.source_url)}" target="_blank" rel="noopener noreferrer">{esc(row.source_name)}</a> ({esc(row.source_type)})'
        f'{f"<br><b>Note</b> {esc(row.notes)}" if row.notes else ""}</p></div>'
    )
with score, st.container(border=True):
    st.markdown('<div class="ptitle">Severity breakdown</div>', unsafe_allow_html=True)
    _html(
        "".join(f'<div class="score-row"><span>{esc(label)}</span><b>+{pts}</b></div>' for label, pts in parts)
        + f'<div class="score-row"><span><b>Total</b></span><b>{row.score} = {esc(row.severity)}</b></div>'
    )

# ---------------------------------------------------------------- 05 method
_html(visuals.section_head("how", "06", "Method and safeguards", "How incidents are verified, scored and kept free of anything sensitive."))
m1, m2 = st.columns(2, gap="medium")
with m1, st.container(border=True):
    st.markdown('<div class="ptitle">Severity rubric</div>', unsafe_allow_html=True)
    st.markdown(
        "Severity is calculated, not opinion. Each record stores its inputs and the score is the sum of the points.\n\n"
        f"- **Scope**: {', '.join(f'{k} {v}' for k, v in SCOPE_POINTS.items())}\n"
        f"- **Service impact**: {', '.join(f'{k} {v}' for k, v in SERVICE_POINTS.items())}\n"
        f"- **Data impact**: {', '.join(f'{k} {v}' for k, v in DATA_POINTS.items())}\n"
        "- **Financial loss**: NPR 1 million = 1, NPR 10 million = 2, NPR 100 million = 3\n"
        "- **Core operational systems affected** (trading, payments, banking core, data centres): 1\n\n"
        "**Low** 0-2, **Medium** 3-4, **High** 5, **Critical** 6 or more."
    )
with m2, st.container(border=True):
    st.markdown('<div class="ptitle">Safeguards</div>', unsafe_allow_html=True)
    st.markdown(
        "- Only public reporting, official disclosures and authorised feeds. Every record links to its source.\n"
        "- No threat-actor names or claims, no indicators of compromise, no vulnerability or exploit detail.\n"
        "- No personal data. Emails, IP addresses, phone numbers, hostnames, hashes and credentials are rejected on load.\n"
        "- Locations are city-level only. Unconfirmed claims are hidden by default and never used to name an attacker.\n"
        "- To correct or remove a record, edit its row in the dataset."
    )
with st.container(border=True):
    st.markdown('<div class="ptitle">Authorised feeds</div>', unsafe_allow_html=True)
    st.markdown(
        "Upload a CSV or JSON file, or set `INCIDENT_FEED_URLS` (comma-separated https URLs) on the server. Every record is validated and "
        "anything with personal data, indicators of compromise or exploit detail is rejected. Uploads live only in this session. "
        "Feed hosts must resolve to public addresses and redirects must stay on the same host.\n\n"
        "Columns: `id, reported_date, category, sector, organisation, title, summary, locations, source_name, source_type, "
        "source_url, verification, scope, service_impact, data_impact, loss_npr_million, critical_systems, notes`."
    )
    st.caption("Source types: " + ", ".join(SOURCE_TYPES))
    st.file_uploader("Feed file", type=["csv", "json"], accept_multiple_files=True, key="feed_upload")

with st.container(border=True):
    st.markdown('<div class="ptitle">Keeping the data current</div>', unsafe_allow_html=True)
    origins = everything["origin"].str.split(":").str[0].value_counts()
    _html(" ".join(theme.chip(f"{name}: {count}") for name, count in origins.items()))
    st.markdown(
        "New incidents reach the dashboard five ways, and every one passes the same validation:\n\n"
        "1. **Live web search**: choose it under *Data source* and press *Scan the live web now*. It reads the RSS feeds of Google News searches and four Nepali outlets, "
        "keeps only headlines that look like Nepal cyber incidents, and shows them as unreviewed and unrated. Nothing is saved. Set `INCIDENT_LIVE_DISABLED=1` to turn it off.\n"
        "2. **Edit the dataset** (`incidents.csv`) and redeploy.\n"
        f"3. **Point at a feed**: set `INCIDENT_FEED_URLS` to a CSV or JSON file (for example a raw file in a repository). "
        f"It is re-read every {data.feed_ttl_seconds() // 60} minutes (`INCIDENT_FEED_TTL` seconds).\n"
        "4. **Add in the app**: set `INCIDENT_DATA_DIR` and `INCIDENT_ADMIN_TOKEN` on a server with persistent storage to unlock the maintainer form below.\n"
        "5. **Upload a file** for a private, session-only view.\n\n"
        "To publish a live result, open its source, check the facts, then add it through option 2, 3 or 4 with a proper severity."
    )
    if st.button("Refresh data now"):
        st.cache_data.clear()
        st.rerun()

if data.admin_enabled():
    with st.container(border=True):
        st.markdown('<div class="ptitle">Maintainers: add an incident</div>', unsafe_allow_html=True)
        st.caption("Needs a public source. The record is validated like every other source and appears for everyone on the next page load.")
        token = st.text_input("Maintainer token", type="password", key="admin_token")
        bad_tokens = st.session_state.setdefault("bad_tokens", set())
        if token and not data.admin_token_ok(token):
            bad_tokens.add(token)
        if len(bad_tokens) >= 5:
            st.error("Too many wrong tokens in this session.")
        elif token and data.admin_token_ok(token):
            if flash := st.session_state.pop("flash", None):
                st.success(flash)
            with st.form("add_incident", clear_on_submit=True):
                f1, f2 = st.columns(2)
                reported = f1.date_input("Reported date", value=date.today(), max_value=date.today())
                category = f2.selectbox("Category", CATEGORIES)
                sector = f1.selectbox("Sector", SECTORS)
                organisation = f2.text_input("Organisation (only if the source names it)")
                title = st.text_input("Title")
                summary = st.text_area("Summary: what the source reported. No attacker names, no technical or exploit detail.")
                places = st.multiselect("Locations (city level)", [*GAZETTEER, NATIONWIDE], default=[NATIONWIDE])
                g1, g2, g3 = st.columns(3)
                source_name = g1.text_input("Source name")
                source_type = g2.selectbox("Source type", SOURCE_TYPES, index=2)
                source_url = g3.text_input("Source link (https)")
                h1, h2, h3, h4 = st.columns(4)
                verification = h1.selectbox("Verification", VERIFICATION, index=1)
                scope = h2.selectbox("Scope", list(SCOPE_POINTS))
                service = h3.selectbox("Service impact", list(SERVICE_POINTS))
                data_impact = h4.selectbox("Data impact", list(DATA_POINTS))
                loss = st.number_input("Financial loss in NPR million (0 if unknown)", min_value=0.0, step=1.0)
                critical = st.checkbox("Core operational systems affected")
                notes = st.text_input("Notes (optional)")
                if st.form_submit_button("Validate and publish"):
                    problems = data.append_local_row({
                        "id": data.next_local_id(reported.year), "reported_date": reported.isoformat(), "category": category, "sector": sector,
                        "organisation": organisation, "title": title, "summary": summary, "locations": ";".join(places),
                        "source_name": source_name, "source_type": source_type, "source_url": source_url, "verification": verification,
                        "scope": scope, "service_impact": service, "data_impact": data_impact, "loss_npr_million": f"{loss:g}" if loss else "",
                        "critical_systems": "true" if critical else "false", "notes": notes,
                    })
                    if problems:
                        st.error("Not published: " + "; ".join(problems))
                    else:
                        st.session_state["flash"] = "Published. It is now in the dataset."
                        st.rerun()

if result.rejected:
    with st.expander(f"{len(result.rejected)} record(s) rejected during validation"):
        for item in result.rejected:
            st.markdown(f"**{esc(item.origin)} / {esc(item.record)}**: " + esc("; ".join(item.problems)))
