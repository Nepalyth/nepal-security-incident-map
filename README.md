# nepal-security-incident-map

🛡️🚨 **Nepal Cyber Incident Map** (नेपाल साइबर घटना नक्सा): a single-page, glass-style cyber dashboard with an incident radar map, a story timeline and historical trends of cybersecurity incidents that were **publicly reported or officially disclosed** in Nepal. Built with Streamlit and Plotly, with a Himalayan skyline hero, the Nepal flag and a live signal ticker.

## What you get

One scrolling page with a fixed top bar that jumps to each section. Filters sit at the top and every section follows them. A **Light mode** switch in the top bar turns the night-sky look into a Himalayan dawn (open `?theme=light` to start in light mode). Every chart has axis titles, value labels, call-outs for the busiest year and the Critical incidents, and a one-line takeaway computed from the filtered data.

| Section | Contents |
| --- | --- |
| Cyber globe | An interactive 3D dotted globe in the style of a live cyber map: drag to rotate, Globe / Nepal / Spin buttons, a pulsing Nepal hub that opens into city beacons when you zoom in, hover cards, and live counters by categoUnlike a sensor network such as Kaspersky Cybermap, this globe shows reported incidents, not live traffic. It draws no attack arcs because public reports rarely say where an attack came from, and guessing would be an unverified accusation. Real-time telemetry needs a data provider; feed it in through an authorised feed and it will show up here.ry. Amber dashed rings mark unreviewed live web headlines |
| Incident radar | Offline map of Nepal with province shading, pulsing city pins coloured by severity, hover cards, and a latest-reports feed with Bikram Sambat dates |
| Timeline | A stem ("lollipop") chart of every report by year, severity band and category, then an alternating story timeline grouped by year, newest first |
| Historical trends | Incidents per year by category, sector-by-year heatmap, severity by year, cumulative reports, verification mix, plus official Nepal Police Cyber Bureau case counts for context |
| Incident log | Filterable table, CSV export, and a detail card with the severity breakdown and source link |
| Method and safeguards | Severity rubric, safeguards and feed upload |

Every record carries: **category** (ransomware, data exposure, phishing, defacement, service disruption, financial fraud), **reported date**, **affected sector**, **source** (name, type, link), **verification status** and a calculated **severity**.

## Screenshots

**Nepal Cyber Incident Map**

![Nepal Cyber Incident Map dashboard](docs/screenshots/nepal%20cyber%20incident%20map.png)

**Incident radar**

![Incident radar map of Nepal with latest reports](docs/screenshots/incident%20radar.png)

## Run

> Prerequisite: [uv](https://docs.astral.sh/uv/getting-started/installation/)

1. Create and activate `venv`

```bash
uv venv
source .venv/bin/activate
```

2. Install Dependencies

```bash
uv sync
```

3. Run app

```bash
uv run app      # or: uv run streamlit run streamlit_app.py
```

4. Tests

```bash
uv run pytest
```

The map is drawn from bundled province outlines as inline SVG, so it needs no map tiles, WebGL or external services.

## Safeguards by design

- Public reporting, official disclosures and authorised feeds only. Every record links to its source.
- The schema has **no field** for threat-actor names, indicators of compromise, vulnerability or exploit detail, or personal data.
- On load, any text containing an email address, IP address, phone number, hostname or URL, file hash, credential material, exploit wording or markup is **rejected** with a reason.
- Locations come from a city-level gazetteer. Nationwide and sector-wide incidents are counted but not plotted.
- Verification tiers: **Confirmed** (acknowledged by the victim, a regulator or police), **Reported** (credible media or researchers) and **Claimed** (third-party claim). Claimed records are hidden by default and are never used to name an attacker.
- Severity is computed from stored inputs, not opinion:

  | Factor | Points |
  | --- | --- |
  | Scope: single organisation / sector-wide / national-level | 1 / 2 / 3 |
  | Service impact: none / degraded / outage | 0 / 1 / 2 |
  | Data impact: none / limited / large-scale | 0 / 1 / 2 |
  | Financial loss: NPR 1 m / 10 m / 100 m | 1 / 2 / 3 |
  | Core operational systems affected | 1 |

  Low 0-2, Medium 3-4, High 5, Critical 6 or more.

## Data

The bundled dataset is [src/nepal_incident_map/data/incidents.csv](src/nepal_incident_map/data/incidents.csv). It is a **small, curated starting set** compiled from public news reports, not a complete register. Counts reflect what was reported, not every attack, and earlier years are thinner. `reported_date` is the date of the earliest source used, which can be a few days after the incident.

Columns: `id, reported_date, category, sector, organisation, title, summary, locations, source_name, source_type, source_url, verification, scope, service_impact, data_impact, loss_npr_million, critical_systems, notes`. `locations` is a `;`-separated list of names from [geo.py](src/nepal_incident_map/geo.py) or `Nationwide`.

To correct or remove a record, edit its row (or delete it) and re-run the tests; the suite fails if any bundled row violates the rules above.

### Keeping the data current

New incidents reach the dashboard five ways. Every one passes the same validation, so nothing sensitive gets in.

### Live web search

Choose **Live web search** or **Both** under *Data source*, then press **Scan the live web now**. The app reads public RSS feeds (six Google News searches such as "Nepal ransomware", plus The Kathmandu Post, Onlinekhabar English, TechPana and ICT Frame), keeps headlines that look like Nepal cyber incidents, and shows them next to the curated CSV.

- **Headlines only.** It reads title, link and date from feeds meant for syndication. It never opens article pages, copies article text or stores anything.
- **Unreviewed and unrated.** Category, sector and city come from keyword rules and can be wrong, so live results are tagged *LIVE WEB / UNREVIEWED*, shown grey with severity *Unrated*, and repeated stories are collapsed. Results already in the curated CSV are dropped.
- **Polite.** One network scan per look-back window every five minutes, shared by all visitors; each feed has a short timeout, a 2 MB cap, and a DTD/entity ban for XML. Redirects are only followed within the same host.
- **Publish after checking.** To make a live result part of the record, read the source, then add it through the CSV, a feed or the maintainer form with a real severity.
- Set `INCIDENT_LIVE_DISABLED=1` to switch it off, for example where a news provider's terms don't allow this use.
- Turn on **Auto-refresh every 5 minutes** to re-check in the background; the page (including the globe) redraws only when a new headline appears.

The globe shows reported incidents, not sensor traffic like Kaspersky Cybermap, and deliberately draws **no attack arcs**: reports rarely say where an attack came from, so arcs would be unverified accusations. It runs offline from a bundled dotted land map (Natural Earth, public domain) inside an isolated iframe, and writes record text with `textContent` only. Genuine real-time telemetry needs a provider; its output can be added as an authorised feed.

| Way | How | Best for |
| --- | --- | --- |
| Edit the dataset | Add a row to `incidents.csv` and redeploy | A small team using Git |
| Feed URL | Set `INCIDENT_FEED_URLS` to comma-separated https links to a CSV or JSON file (for example a raw file in a repository). It is re-read every 15 minutes, or every `INCIDENT_FEED_TTL` seconds (minimum 30) | Hosts with a read-only or temporary disk, such as Streamlit Community Cloud: commit the file and the site updates itself |
| Maintainer form | Set `INCIDENT_DATA_DIR` (a persistent folder) and `INCIDENT_ADMIN_TOKEN`. A form appears in the Method section; records are validated and saved to `incidents_local.csv`, and show for everyone on the next page load | A server or VM you control |
| Upload | Drop a CSV or JSON file in the Method section; it lives only in that browser session | Checking a file before publishing it |

The maintainer form is off unless both variables are set, compares the token in constant time and locks after five wrong tokens in a session. The **Refresh data now** button clears the caches immediately. Feed hosts must resolve to public addresses, redirects must stay on the same host, and responses are limited to 2 MB and 2,000 records.

JSON feeds can be a list of objects or `{"incidents": [...]}`.
