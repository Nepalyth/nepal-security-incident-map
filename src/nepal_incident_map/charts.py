"""Annotated Plotly figures and plain-language takeaways, themed for dark or light mode."""

from __future__ import annotations

import html

import pandas as pd
import plotly.graph_objects as go

from nepal_incident_map import data
from nepal_incident_map.schema import CATEGORIES, SEVERITIES
from nepal_incident_map.theme import CATEGORY_COLORS, SEVERITY_COLORS, STATUS_COLORS, Palette, palette

_DARK = palette(False)


def _short(text: str, limit: int = 34) -> str:
    return html.escape(text if len(text) <= limit else text[: limit - 1].rstrip() + "…")


def _layout(fig: go.Figure, p: Palette, height: int, **extra) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color=p.text, size=12),
        legend=dict(font=dict(color=p.muted, size=11), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=p.hover_bg, bordercolor=p.accent, font=dict(color=p.text)),
    )
    fig.update_layout(**extra)
    fig.update_xaxes(gridcolor=p.grid, zerolinecolor=p.grid, linecolor=p.grid, tickfont=dict(color=p.muted))
    fig.update_yaxes(gridcolor=p.grid, zerolinecolor=p.grid, linecolor=p.grid, tickfont=dict(color=p.muted))
    return fig


def _titles(fig: go.Figure, p: Palette, x: str | None = None, y: str | None = None) -> None:
    font = dict(size=11, color=p.muted)
    if x:
        fig.update_xaxes(title=dict(text=x, font=font, standoff=16))
    if y:
        fig.update_yaxes(title=dict(text=y, font=font, standoff=8))


def _year_range(df: pd.DataFrame) -> list[int]:
    return list(range(int(df["year"].min()), int(df["year"].max()) + 1))


def _stack_totals(fig: go.Figure, p: Palette, years: list[int], totals: list[int]) -> None:
    # Category axes place annotations by position index; string x values are read as numbers.
    for position, total in enumerate(totals):
        if total:
            fig.add_annotation(x=position, y=total, text=f"<b>{total}</b>", showarrow=False, yshift=11, font=dict(size=12, color=p.text))


def timeline_figure(df: pd.DataFrame, p: Palette = _DARK) -> go.Figure:
    """Lollipop timeline: one stem per report, height = severity band, colour = category."""
    unrated_y = 0.5
    heights = df["score"].where(df["score"] > 0, unrated_y)
    y_max = max(float(heights.max()), 6.0) + 3.4
    symbols = {"Confirmed": "circle", "Reported": "diamond", "Claimed": "circle-open"}
    fig = go.Figure()

    years = list(range(int(df["year"].min()), int(df["year"].max()) + 1))
    for year in years:
        if year % 2 == 0:
            fig.add_shape(type="rect", xref="x", yref="paper", x0=f"{year}-01-01", x1=f"{year + 1}-01-01", y0=0, y1=1,
                          fillcolor=p.soft, line_width=0, layer="below")
    for name, low, high in (("Low", 0.75, 2.5), ("Medium", 2.5, 4.5), ("High", 4.5, 5.5), ("Critical", 5.5, y_max)):
        fig.add_shape(type="rect", xref="paper", yref="y", x0=0, x1=1, y0=low, y1=high, line_width=0, layer="below",
                      fillcolor=SEVERITY_COLORS[name], opacity=0.07 if not p.light else 0.10)
        fig.add_annotation(xref="paper", yref="y", x=0.002, y=(low + min(high, 7.0)) / 2, text=name.upper(), showarrow=False, xanchor="left",
                           font=dict(size=10, color=SEVERITY_COLORS[name] if not p.light else p.muted, family="JetBrains Mono, monospace"))

    for category in CATEGORIES:
        part = df[df["category"] == category]
        if part.empty:
            continue
        y = heights.loc[part.index]
        stem_x, stem_y = [], []
        for day, top in zip(part["date"], y):
            stem_x += [day, day, None]
            stem_y += [0, top, None]
        fig.add_trace(go.Scatter(x=stem_x, y=stem_y, mode="lines", line=dict(color=CATEGORY_COLORS[category], width=2), opacity=0.55,
                                 hoverinfo="skip", showlegend=False, legendgroup=category))
        fig.add_trace(go.Scatter(
            x=part["date"], y=y, mode="markers", name=category, legendgroup=category,
            marker=dict(size=15, color=CATEGORY_COLORS[category], symbol=part["verification"].map(symbols), line=dict(width=2, color=p.edge)),
            customdata=part[["title", "verification", "severity", "sector"]].map(html.escape).to_numpy(),
            hovertemplate="<b>%{customdata[0]}</b><br>%{x|%d %b %Y} | %{customdata[3]}<br>"
                          f"{html.escape(category)} | %{{customdata[2]}} | %{{customdata[1]}}<extra></extra>",
        ))

    flagged = df[df["severity"].isin(["Critical", "High"])].sort_values("date")
    start = pd.Timestamp(f"{years[0]}-01-01")
    late = pd.Timestamp(f"{years[-1]}-01-01") - pd.Timedelta(days=200)
    per_year = 880 / max((pd.Timestamp(f"{years[-1] + 1}-01-01") - start).days / 365.25, 1)  # rough pixels per year
    rows_taken: dict[int, list[tuple[float, float]]] = {}
    label_rows = [y_max - 0.6 - 0.85 * n for n in range(4)]  # fixed label rows above the data, in axis units
    for row in flagged.itertuples():
        text = _short(row.title, 24)
        left = row.date >= late  # labels near the right edge open leftwards so they stay inside the plot
        x = (row.date - start).days / 365.25
        width = (len(text) * 5.4 + 20) / per_year
        lo, hi = (x - width, x) if left else (x, x + width)
        level = next((n for n in range(len(label_rows)) if all(hi < a - 0.05 or lo > b + 0.05 for a, b in rows_taken.get(n, []))), len(label_rows) - 1)
        rows_taken.setdefault(level, []).append((lo, hi))
        fig.add_annotation(
            x=row.date, y=heights.loc[row.Index], ax=row.date, ay=label_rows[level], axref="x", ayref="y", text=text, showarrow=True, arrowhead=0,
            arrowwidth=1, arrowcolor=CATEGORY_COLORS[row.category], xanchor="right" if left else "left", font=dict(size=10, color=p.text),
            bgcolor=p.hover_bg, bordercolor=CATEGORY_COLORS[row.category], borderpad=3, opacity=0.96,
        )
    for day, label, short in data.MILESTONES:
        x = day.isoformat()
        fig.add_shape(type="line", x0=x, x1=x, y0=0, y1=1, yref="paper", line=dict(color=p.accent, width=1, dash="dot"))
        fig.add_annotation(x=x, y=0, yref="paper", text=html.escape(short), hovertext=html.escape(label), showarrow=False, xanchor="left", yanchor="bottom",
                           font=dict(size=10, color=p.accent), xshift=6, yshift=8, captureevents=True)

    fig = _layout(fig, p, 480, margin=dict(l=8, r=8, t=40, b=8),
                  legend=dict(orientation="h", x=0, y=1.14, title=dict(text="Category  ", font=dict(color=p.muted, size=11)), font=dict(color=p.muted)))
    fig.update_xaxes(range=[f"{years[0]}-01-01", f"{years[-1] + 1}-01-01"], tickvals=[f"{y}-07-01" for y in years], ticktext=[str(y) for y in years],
                     showgrid=False, ticks="")
    fig.update_yaxes(range=[0, y_max], showticklabels=False, showgrid=False, zeroline=True, zerolinecolor=p.muted, zerolinewidth=1)
    _titles(fig, p, x="Year reported (stem height = severity band, marker shape = verification)")
    return fig


def yearly_stacked(df: pd.DataFrame, p: Palette = _DARK) -> go.Figure:
    years = _year_range(df)
    counts = df.groupby(["year", "category"]).size().unstack(fill_value=0).reindex(years, fill_value=0)
    totals = counts.sum(axis=1)
    fig = go.Figure()
    for category in CATEGORIES:
        if category in counts:
            fig.add_trace(go.Bar(x=[str(y) for y in years], y=counts[category], name=category, marker_color=CATEGORY_COLORS[category],
                                 hovertemplate=f"{category}: %{{y}}<extra>%{{x}}</extra>"))
    _stack_totals(fig, p, years, [int(t) for t in totals])
    peak_year = int(totals.idxmax())
    fig.add_annotation(x=years.index(peak_year), y=int(totals.max()), text=f"Busiest year: {peak_year}", showarrow=True, arrowhead=2, arrowcolor=p.accent,
                       ax=-70, ay=-34, font=dict(size=11, color=p.accent), bgcolor=p.hover_bg, bordercolor=p.accent, borderpad=3)
    fig = _layout(fig, p, 360, barmode="stack", legend=dict(orientation="h", y=-0.28, font=dict(color=p.muted)))
    fig.update_yaxes(dtick=1, range=[0, int(totals.max()) + 1.6])
    fig.update_xaxes(type="category")
    _titles(fig, p, x="Year reported", y="Number of reported incidents")
    return fig


def _donut(labels: pd.Index, values: list[int], colors: list[str], p: Palette, centre: str) -> go.Figure:
    fig = go.Figure(go.Pie(
        labels=list(labels), values=values, hole=0.62, sort=False, textinfo="percent", textfont=dict(size=12, color="#0b1b3a"),
        marker=dict(colors=colors, line=dict(color=p.edge, width=2)), hovertemplate="%{label}: %{value} incident(s), %{percent}<extra></extra>",
    ))
    fig.add_annotation(text=centre, x=0.5, y=0.5, showarrow=False, font=dict(size=14, color=p.text), xref="paper", yref="paper")
    return _layout(fig, p, 360, showlegend=True, legend=dict(orientation="h", y=-0.06, font=dict(color=p.muted, size=11)))


def category_donut(df: pd.DataFrame, p: Palette = _DARK) -> go.Figure:
    counts = df["category"].value_counts()
    return _donut(counts.index, list(counts.values), [CATEGORY_COLORS[c] for c in counts.index], p, f"<span style='font-size:26px'><b>{len(df)}</b></span><br>incidents")


def status_donut(df: pd.DataFrame, p: Palette = _DARK) -> go.Figure:
    counts = df["verification"].value_counts()
    return _donut(counts.index, list(counts.values), [STATUS_COLORS[s] for s in counts.index], p, f"<span style='font-size:26px'><b>{len(df)}</b></span><br>records")


def sector_heatmap(df: pd.DataFrame, p: Palette = _DARK) -> go.Figure:
    years = _year_range(df)
    grid = df.groupby(["sector", "year"]).size().unstack(fill_value=0).reindex(columns=years, fill_value=0)
    grid = grid.loc[grid.sum(axis=1).sort_values().index]
    scale = [[0, "#bfe8f1"], [1, "#2aa5bd"]] if p.light else [[0, "#0f8fa3"], [1, "#7ff3ff"]]
    fig = go.Figure(go.Heatmap(
        z=grid.where(grid > 0).to_numpy(), x=[str(y) for y in years], y=list(grid.index), xgap=3, ygap=3, colorscale=scale, showscale=False,
        texttemplate="%{z}", textfont=dict(color="#021018", size=13), hovertemplate="%{y}, %{x}: %{z} incident(s)<extra></extra>",
    ))
    fig = _layout(fig, p, 360)
    fig.update_xaxes(type="category")
    fig.update_yaxes(tickfont=dict(color=p.text))
    _titles(fig, p, x="Year reported (number in each cell = incidents)", y="Sector")
    return fig


def severity_by_year(df: pd.DataFrame, p: Palette = _DARK) -> go.Figure:
    years = _year_range(df)
    counts = df.groupby(["year", "severity"]).size().unstack(fill_value=0).reindex(years, fill_value=0)
    fig = go.Figure()
    for severity in SEVERITIES:
        if severity in counts:
            fig.add_trace(go.Bar(x=[str(y) for y in years], y=counts[severity], name=severity, marker_color=SEVERITY_COLORS[severity],
                                 hovertemplate=f"{severity}: %{{y}}<extra>%{{x}}</extra>"))
    totals = counts.sum(axis=1)
    _stack_totals(fig, p, years, [int(t) for t in totals])
    fig = _layout(fig, p, 360, barmode="stack", legend=dict(orientation="h", y=-0.28, font=dict(color=p.muted)))
    fig.update_yaxes(dtick=1, range=[0, int(totals.max()) + 1.6])
    fig.update_xaxes(type="category")
    _titles(fig, p, x="Year reported", y="Number of reported incidents")
    return fig


def cumulative_figure(df: pd.DataFrame, p: Palette = _DARK) -> go.Figure:
    ordered = df.sort_values("date").reset_index(drop=True)
    ordered["n"] = ordered.index + 1
    fig = go.Figure(go.Scatter(
        x=ordered["date"], y=ordered["n"], mode="lines+markers", line=dict(color=p.accent, width=2, shape="hv"),
        marker=dict(size=7, color=p.accent), fill="tozeroy", fillcolor=p.soft,
        hovertemplate="%{x|%d %b %Y}: %{y} reported so far<extra></extra>",
    ))
    for row in ordered[ordered["severity"] == "Critical"].itertuples():
        fig.add_annotation(x=row.date, y=row.n, text="Critical: " + _short(row.title, 30), showarrow=True, arrowhead=2, arrowcolor=SEVERITY_COLORS["Critical"],
                           ax=-90, ay=-38, font=dict(size=10, color=p.text), bgcolor=p.hover_bg, bordercolor=SEVERITY_COLORS["Critical"], borderpad=3)
    last = ordered.iloc[-1]
    fig.add_annotation(x=last["date"], y=last["n"], text=f"<b>{int(last['n'])}</b> to date", showarrow=False, xanchor="right", yshift=14, font=dict(size=11, color=p.accent))
    fig = _layout(fig, p, 360)
    fig.update_yaxes(range=[0, int(last["n"]) + 1.5])
    _titles(fig, p, x="Date reported", y="Total reported so far")
    return fig


def official_stats_figure(p: Palette = _DARK) -> go.Figure:
    stats = data.CYBER_BUREAU_STATS
    fig = go.Figure()
    fig.add_trace(go.Bar(x=stats["fiscal_year"], y=stats["registered_cases"], name="All registered cybercrime cases", marker_color="#3d7bff",
                         texttemplate="%{y:,}", textposition="outside", textfont=dict(color=p.text)))
    fig.add_trace(go.Bar(x=stats["fiscal_year"], y=stats["financial_fraud"], name="Financial scams and fraud", marker_color="#dc143c",
                         texttemplate="%{y:,}", textposition="outside", textfont=dict(color=p.text)))
    growth = stats["financial_fraud"].iloc[-1] / stats["financial_fraud"].iloc[0] - 1
    fig.add_annotation(x=len(stats) - 1, y=int(stats["financial_fraud"].iloc[-1]) + 2600, text=f"<b>{growth:+.1%}</b> scams and fraud",
                       showarrow=True, arrowhead=2, arrowcolor="#dc143c", ax=-40, ay=-40, font=dict(size=11, color=p.text), bgcolor=p.hover_bg, bordercolor="#dc143c", borderpad=3)
    fig = _layout(fig, p, 360, barmode="group", legend=dict(orientation="h", y=-0.22, font=dict(color=p.muted)))
    fig.update_yaxes(range=[0, 24_000])
    _titles(fig, p, x="Fiscal year", y="Cases registered by Nepal Police Cyber Bureau")
    return fig


def insights(df: pd.DataFrame) -> dict[str, str]:
    """One-sentence takeaways (HTML-safe) shown above each chart; all values come from the filtered data."""
    by_year = df["year"].value_counts().sort_index()
    top_year, top_count = int(by_year.idxmax()), int(by_year.max())
    categories, sectors = df["category"].value_counts(), df["sector"].value_counts()
    severe = df[df["severity"].isin(["High", "Critical"])]
    rated = df[df["score"] > 0]
    worst = rated.sort_values(["score", "date"], ascending=[False, False]).iloc[0] if len(rated) else None
    confirmed = (df["verification"] == "Confirmed").mean()
    first, last = df["date"].min(), df["date"].max()
    s = "s" if len(df) != 1 else ""
    return {
        "yearly": f"<b>{top_year}</b> has the most reports ({top_count}). The most common type overall is <b>{html.escape(categories.index[0])}</b> ({categories.iloc[0]} of {len(df)}).",
        "category": f"<b>{categories.iloc[0] / len(df):.0%}</b> of the reports are <b>{html.escape(categories.index[0])}</b>. Hover a slice for the count.",
        "sector": f"<b>{html.escape(sectors.index[0])}</b> appears most often ({sectors.iloc[0]} of {len(df)}). Darker cells mean more reports that year.",
        "severity": (f"<b>{len(severe)}</b> of {len(rated)} rated reports are High or Critical. The most severe: <b>{html.escape(worst['title'])}</b> ({worst['date']:%b %Y})."
                     + (f" {len(df) - len(rated)} unreviewed live result(s) are not rated." if len(df) > len(rated) else "")) if worst is not None else "None of the reports in view have been rated yet.",
        "cumulative": f"<b>{len(df)}</b> report{s} between {first:%b %Y} and {last:%b %Y}. Steeper steps mean more reports in a short time; red callouts mark Critical incidents.",
        "status": f"<b>{confirmed:.0%}</b> of the records are confirmed by the victim or an authority; the rest rest on credible media or research.",
        "official": "Registered cases barely moved, but <b>financial scams and fraud</b> nearly doubled. These are police case counts, not the incidents mapped here.",
    }
