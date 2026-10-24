import base64
import json
import re

from nepal_incident_map import data, globe, live


def _frame():
    return data.build_frame(("bundled", r) for r in data.load_seed_rows()).incidents


def test_payload_has_a_hub_beacons_and_counters():
    p = globe.payload(_frame(), light=False)
    assert p["hub"]["n"] == 11 and p["hub"]["severity"] == "Critical"
    names = {b["name"] for b in p["beacons"]}
    assert {"Kathmandu", "Biratnagar", "Nationwide"} <= names
    kathmandu = next(b for b in p["beacons"] if b["name"] == "Kathmandu")
    assert kathmandu["n"] == 7 and kathmandu["severity"] == "Critical"
    assert sum(c["n"] for c in p["counters"]) == 11
    assert len(p["coarse"]) > 1000 and len(p["nepal"]) >= 7


def test_live_results_are_flagged_and_unrated_on_the_globe():
    item = live.RawItem("Ransomware attack halts Nepal stock market", "https://news.example.com/1", data.date.today(), "Example")
    row = live.to_row(item, live.PUBLISHER_FEEDS[0])
    frame = data.build_frame([("web", row)]).incidents
    p = globe.payload(frame, light=True)
    assert p["live"] == 1 and p["hub"]["severity"] == "Unrated" and p["beacons"][0]["live"] == 1
    assert p["palette"]["fg"] == "#10244a"


def test_empty_view_does_not_break_the_globe():
    p = globe.payload(_frame().iloc[0:0], light=False)
    assert p["hub"]["n"] == 0 and p["beacons"] == [] and p["counters"] == []


def test_hostile_titles_cannot_break_out_of_the_script_block():
    frame = _frame()
    frame.loc[0, "title"] = "</script><script>alert(1)</script><!-- x"
    html = globe.globe_html(frame, light=False)
    assert html.count("</script>") == 1 and "<!--" not in html.split("<script>", 1)[1]
    blob = re.search(r"const D=(\{.*?\}),P=D\.palette", html, re.S).group(1)
    assert json.loads(blob.replace("\\/", "/"))["hub"]["n"] == 11


def test_globe_is_served_as_an_isolated_data_url():
    src = globe.globe_src(_frame(), light=False)
    assert src.startswith("data:text/html;charset=utf-8;base64,")
    assert b"NEPAL // CYBER GLOBE" in base64.b64decode(src.split(",", 1)[1])
    assert "innerHTML" not in globe._TEMPLATE
