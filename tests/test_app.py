from pathlib import Path

from streamlit.testing.v1 import AppTest

from nepal_incident_map import charts, data, visuals

APP = str(Path(__file__).parent.parent / "streamlit_app.py")


def _frame():
    return data.build_frame(("bundled", r) for r in data.load_seed_rows()).incidents


def test_every_figure_builds_for_the_bundled_data():
    frame = _frame()
    figures = [
        charts.timeline_figure(frame), charts.yearly_stacked(frame),
        charts.category_donut(frame), charts.sector_heatmap(frame), charts.severity_by_year(frame),
        charts.cumulative_figure(frame), charts.status_donut(frame), charts.official_stats_figure(),
    ]
    assert all(fig.data for fig in figures)


def test_html_blocks_are_single_line_and_escape_record_text():
    frame = _frame()
    frame.loc[0, "title"] = "<img src=x onerror=alert(1)>"
    blocks = [visuals.nav_html(), visuals.hero_html(frame, len(frame)), visuals.map_html(frame), visuals.feed_html(frame), visuals.timeline_html(frame)]
    for block in blocks:
        assert "\n" not in block and "<img" not in block
    assert "&lt;img" in visuals.timeline_html(frame)


def test_map_html_has_one_pin_per_city_plus_nationwide():
    frame = _frame()
    html = visuals.map_html(frame)
    assert html.count("class='pin") == 5 + 1 and "Nationwide" in html
    assert "class='pin" not in visuals.map_html(frame.iloc[0:0])


def test_flag_has_border_moon_and_sun():
    svg = visuals.flag_svg(50, "t")
    assert "#dc143c" in svg and "#003893" in svg and svg.count("<polygon") == 3


def test_app_runs_and_filters_without_errors():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    at.text_input[0].set_value("ransomware").run()
    assert not at.exception
    at.text_input[0].set_value("zzz-no-match").run()
    assert not at.exception and at.info


def test_figures_build_in_light_mode_and_insights_cover_every_chart():
    from nepal_incident_map import theme

    frame, light = _frame(), theme.palette(True)
    figures = [
        charts.timeline_figure(frame, light), charts.yearly_stacked(frame, light), charts.category_donut(frame, light),
        charts.sector_heatmap(frame, light), charts.severity_by_year(frame, light), charts.cumulative_figure(frame, light),
        charts.status_donut(frame, light), charts.official_stats_figure(light),
    ]
    assert all(fig.data for fig in figures)
    assert set(charts.insights(frame)) == {"yearly", "category", "sector", "severity", "cumulative", "status", "official"}
    assert charts.timeline_figure(frame).layout.annotations


def test_charts_are_annotated():
    frame = _frame()
    assert len(charts.yearly_stacked(frame).layout.annotations) >= 3
    assert charts.yearly_stacked(frame).layout.xaxis.title.text and charts.yearly_stacked(frame).layout.yaxis.title.text
    assert any("Critical" in a.text for a in charts.cumulative_figure(frame).layout.annotations)


def test_light_mode_toggle_runs_without_errors():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert at.toggle[0].value is False
    at.toggle[0].set_value(True).run()
    assert not at.exception and at.session_state["light_mode"] is True
    assert "--bg:#e9f0fb" in "".join(m.value for m in at.markdown)


def test_maintainer_form_is_hidden_unless_configured(monkeypatch, tmp_path):
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not any("Maintainers" in m.value for m in at.markdown)
    monkeypatch.setenv("INCIDENT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("INCIDENT_ADMIN_TOKEN", "s3cret")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert any("Maintainers" in m.value for m in at.markdown) and not at.exception
