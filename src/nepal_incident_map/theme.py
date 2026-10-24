"""Glass-morphism cyber theme (dark and light) with Nepali accents: dhaka border, crimson and blue, Himalayan skyline."""

from __future__ import annotations

import html
from dataclasses import dataclass

import streamlit as st

SEVERITY_COLORS = {"Low": "#5fd38d", "Medium": "#ffc233", "High": "#ff7a3d", "Critical": "#ff3b6b"}
STATUS_COLORS = {"Confirmed": "#2de6a6", "Reported": "#29d3ff", "Claimed": "#ffc233"}
CATEGORY_COLORS = {
    "Ransomware": "#ff3b6b", "Data exposure": "#b57bff", "Phishing": "#ffc233",
    "Defacement": "#ff7a3d", "Service disruption": "#29d3ff", "Financial fraud": "#2de6a6",
}
TEXT, MUTED, CYAN, CRIMSON = "#dbe7ff", "#8fa3c7", "#00e5ff", "#dc143c"


@dataclass(frozen=True)
class Palette:
    """Colours that Plotly figures need, because CSS variables cannot reach into SVG chart text."""

    light: bool
    text: str
    muted: str
    grid: str
    edge: str
    hover_bg: str
    accent: str
    on_accent: str
    soft: str


def palette(light: bool) -> Palette:
    if light:
        return Palette(True, "#10244a", "#51668f", "rgba(20,60,120,0.12)", "#f4f8ff", "#ffffff", "#007c96", "#ffffff", "rgba(0,124,150,0.10)")
    return Palette(False, TEXT, MUTED, "rgba(255,255,255,0.07)", "#05080f", "#0a1222", CYAN, "#021018", "rgba(0,229,255,0.10)")


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=JetBrains+Mono:wght@400;500;700&family=Mukta:wght@500;600&family=Inter:wght@400;500;600&display=swap');
:root { --bg:#050912; --text:#dbe7ff; --muted:#8fa3c7; --head:#ffffff; --body2:#c3d2ec; --cyan:#00e5ff; --crimson:#dc143c; --blue:#3d7bff;
  --glass:rgba(16,28,54,.46); --stroke:rgba(150,215,255,.20); --line2:rgba(255,255,255,.07); --navbg:rgba(5,9,18,.55); --tipbg:rgba(8,15,32,.84);
  --field:rgba(255,255,255,.06); --maptext:#e8f4ff; --ringbg:rgba(5,9,18,.95); --yearbg:rgba(5,9,18,.9); --chipk:100%; --herop:#aebfdc; --shadow:rgba(0,0,0,.85); }
html, body, .stApp { font-family:'Inter', system-ui, sans-serif; color:var(--text); scroll-behavior:smooth; }
[data-testid="stMain"], section.main { scroll-behavior:smooth; }

/* page: aurora + grid + scanlines behind frosted glass */
.stApp { background:var(--bg); }
.stApp::before { content:""; position:fixed; inset:-20%; z-index:0; pointer-events:none; filter:blur(30px); animation:drift 38s ease-in-out infinite alternate;
  background:radial-gradient(40% 36% at 82% 8%, rgba(0,229,255,.22), transparent 70%), radial-gradient(38% 40% at 6% 30%, rgba(220,20,60,.20), transparent 70%),
    radial-gradient(44% 40% at 60% 96%, rgba(61,123,255,.22), transparent 70%); }
.stApp::after { content:""; position:fixed; inset:0; z-index:0; pointer-events:none;
  background:linear-gradient(rgba(0,229,255,.03) 1px, transparent 1px) 0 0/48px 48px, linear-gradient(90deg, rgba(0,229,255,.03) 1px, transparent 1px) 0 0/48px 48px,
    repeating-linear-gradient(0deg, rgba(255,255,255,.012) 0 1px, transparent 1px 3px); }
@keyframes drift { to { transform:translate3d(3%, 2%, 0) scale(1.06); } }
[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], [data-testid="stToolbar"], footer, #MainMenu { display:none !important; }
.block-container { max-width:1500px; padding:5.2rem 2.2rem 4rem; position:relative; z-index:2; }
a { color:var(--cyan); text-decoration:none; } a:hover { text-decoration:underline; }
h1, h2, h3, h4 { font-family:'Rajdhani', sans-serif !important; letter-spacing:.02em; }

/* glass surfaces: every bordered container */
[data-testid="stVerticalBlockBorderWrapper"] { background:linear-gradient(150deg, rgba(255,255,255,.10), rgba(255,255,255,.015) 55%), var(--glass);
  -webkit-backdrop-filter:blur(20px) saturate(155%); backdrop-filter:blur(20px) saturate(155%); border:1px solid var(--stroke) !important; border-radius:22px;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.16), 0 26px 60px -30px var(--shadow), 0 0 40px -22px rgba(0,229,255,.55); }
.ptitle { font:600 12px 'JetBrains Mono', monospace; letter-spacing:.18em; text-transform:uppercase; color:var(--cyan); margin:2px 0 8px; }
.ptitle::before { content:"// "; color:var(--crimson); }
.note { font-size:12.5px !important; color:var(--muted) !important; line-height:1.5; }
.callout { border:1px dashed rgba(255,194,51,.45); background:rgba(255,194,51,.07); color:#f1dca0; border-radius:14px; padding:10px 14px; font-size:13px; line-height:1.5; }
.insight { font-size:13.5px; line-height:1.5; color:var(--body2); border-left:3px solid var(--cyan); padding:2px 0 2px 12px; margin:0 0 8px; }
.insight b { color:var(--head); }

/* top navigation */
.nav { position:fixed; top:0; left:0; right:0; height:60px; z-index:999; display:flex; align-items:center; justify-content:space-between; padding:0 28px;
  background:var(--navbg); -webkit-backdrop-filter:blur(18px) saturate(160%); backdrop-filter:blur(18px) saturate(160%); border-bottom:1px solid var(--stroke); }
.nav-brand { display:flex; align-items:center; gap:10px; color:var(--head) !important; text-decoration:none !important; font:700 17px 'Rajdhani', sans-serif; letter-spacing:.14em; }
.nav-links { display:flex; gap:4px; }
.nav-links a { font:600 12px 'JetBrains Mono', monospace; letter-spacing:.1em; text-transform:uppercase; color:var(--muted); padding:8px 14px; border-radius:999px; text-decoration:none !important; transition:.2s; }
.nav-links a:hover { color:var(--head); background:rgba(0,229,255,.12); box-shadow:0 0 18px -4px var(--cyan); }
.st-key-themebox { position:fixed; top:11px; right:158px; z-index:1001; width:auto !important; }
.st-key-themebox [data-testid="stWidgetLabel"] p, .st-key-themebox p { font:600 11px 'JetBrains Mono', monospace !important; letter-spacing:.1em; text-transform:uppercase; color:var(--muted) !important; margin:0; }
.st-key-themebox label { align-items:center; }
@media (max-width:820px) { .nav-links { display:none; } .block-container { padding:5rem 1rem 3rem; } .st-key-themebox { right:12px; top:62px; } }

/* hero */
.hero2 { position:relative; overflow:hidden; border-radius:26px; border:1px solid var(--stroke); min-height:640px; margin-bottom:8px;
  background:linear-gradient(180deg, #050a1a 0%, #0a1431 52%, #12214a 100%); box-shadow:0 30px 80px -40px rgba(0,229,255,.55), inset 0 1px 0 rgba(255,255,255,.14); }
.hero2 .aurora { position:absolute; inset:-30%; filter:blur(50px); opacity:.9; animation:drift 24s ease-in-out infinite alternate;
  background:radial-gradient(30% 30% at 70% 22%, rgba(0,229,255,.28), transparent 70%), radial-gradient(28% 30% at 22% 30%, rgba(220,20,60,.26), transparent 70%), radial-gradient(30% 24% at 50% 10%, rgba(120,90,255,.22), transparent 70%); }
.hero2 .peaks { position:absolute; left:0; right:0; bottom:0; width:100%; height:300px; }
.hero2 .tw { animation:twinkle 3.2s ease-in-out infinite; }
@keyframes twinkle { 50% { opacity:.1; } }
.pk-n { font:600 11px 'JetBrains Mono', monospace; fill:#bff3ff; letter-spacing:.06em; } .pk-h { font:400 10px 'JetBrains Mono', monospace; fill:#7fb6d4; }
.hero2-in { position:relative; z-index:2; display:flex; gap:34px; align-items:flex-start; padding:40px 52px 300px; }
.hero2-flag { flex:none; transform-origin:0 50%; animation:sway 6s ease-in-out infinite; filter:drop-shadow(0 0 22px rgba(220,20,60,.65)) drop-shadow(0 8px 14px rgba(0,0,0,.5)); }
@keyframes sway { 0%, 100% { transform:perspective(500px) rotateY(-10deg) skewY(-1deg); } 50% { transform:perspective(500px) rotateY(9deg) skewY(1.5deg); } }
.eyebrow { font:500 11px 'JetBrains Mono', monospace; letter-spacing:.26em; color:var(--cyan); text-transform:uppercase; }
.hero2 h1 { margin:6px 0 0; font-size:clamp(34px, 4.6vw, 64px); line-height:1; font-weight:700; color:#fff; text-shadow:0 0 28px rgba(0,229,255,.45); position:relative; }
.glitch::before, .glitch::after { content:attr(data-t); position:absolute; left:0; top:0; width:100%; opacity:0; pointer-events:none; }
.glitch::before { color:#ff3b6b; clip-path:inset(0 0 55% 0); animation:gl1 6s steps(1) infinite; }
.glitch::after { color:#00e5ff; clip-path:inset(55% 0 0 0); animation:gl2 6s steps(1) infinite; }
@keyframes gl1 { 0%, 91%, 100% { opacity:0; transform:none; } 92% { opacity:.85; transform:translate(4px, -1px); } 94% { opacity:.85; transform:translate(-3px, 1px); } 96% { opacity:0; } }
@keyframes gl2 { 0%, 92%, 100% { opacity:0; transform:none; } 93% { opacity:.85; transform:translate(-4px, 1px); } 95% { opacity:.85; transform:translate(3px, -1px); } 97% { opacity:0; } }
.hero2 .np { font-family:'Mukta', sans-serif; font-size:24px; color:#ffb3c1; margin-top:6px; }
.hero2 p { max-width:720px; color:var(--herop); margin:14px 0 16px; font-size:15.5px; line-height:1.6; }
.ribbon { display:flex; flex-wrap:wrap; gap:8px; }
.ticker { position:absolute; left:0; right:0; bottom:20px; height:40px; z-index:3; display:flex; align-items:center; overflow:hidden;
  background:rgba(5,9,18,.6); -webkit-backdrop-filter:blur(10px); backdrop-filter:blur(10px); border-top:1px solid var(--stroke); border-bottom:1px solid var(--stroke); }
.tk-tag { flex:none; z-index:2; font:700 11px 'JetBrains Mono', monospace; letter-spacing:.2em; color:#fff; background:var(--crimson); padding:0 16px; height:100%; display:flex; align-items:center; box-shadow:0 0 24px rgba(220,20,60,.7); }
.tk-wrap { overflow:hidden; flex:1; }
.tk-track { display:flex; width:max-content; gap:46px; padding-left:30px; animation:tick 80s linear infinite; }
.tk-wrap:hover .tk-track { animation-play-state:paused; }
@keyframes tick { to { transform:translateX(-50%); } }
.tk { white-space:nowrap; font:400 12px 'JetBrains Mono', monospace; color:#c6d6f2; } .tk b { color:var(--c); letter-spacing:.08em; margin-right:6px; } .tk i { color:#4f6a96; font-style:normal; }
.dhaka { position:absolute; left:0; right:0; bottom:0; height:12px; z-index:4; background-color:#0a1222;
  background-image:linear-gradient(135deg,#dc143c 25%,transparent 25%), linear-gradient(225deg,#dc143c 25%,transparent 25%), linear-gradient(315deg,#3d7bff 25%,transparent 25%), linear-gradient(45deg,#3d7bff 25%,transparent 25%);
  background-size:24px 24px; background-position:-12px 0, -12px 0, 0 0, 0 0; }
.live { display:inline-block; width:8px; height:8px; border-radius:50%; background:#2de6a6; margin-right:7px; animation:pulse 2s infinite; }
@keyframes pulse { 0% { box-shadow:0 0 0 0 rgba(45,230,166,.7); } 70%, 100% { box-shadow:0 0 0 9px rgba(45,230,166,0); } }
@media (max-width:760px) { .hero2-in { flex-direction:column; padding:30px 22px 300px; } }

/* chips */
.chip { display:inline-block; font:500 11px 'JetBrains Mono', monospace; letter-spacing:.05em; padding:3px 9px; border-radius:999px; color:color-mix(in srgb, var(--c) var(--chipk), #0b1b3a);
  border:1px solid color-mix(in srgb, var(--c) 55%, transparent); background:color-mix(in srgb, var(--c) 12%, transparent); white-space:nowrap; }
.chip.plain { --c:#a9bddf; }

/* section headings */
.sec { margin:40px 0 14px; scroll-margin-top:84px; display:flex; align-items:flex-end; justify-content:space-between; gap:10px 30px; flex-wrap:wrap; }
.sec .n { font:600 12px 'JetBrains Mono', monospace; letter-spacing:.2em; color:var(--crimson); }
.sec h2 { margin:0; font:700 34px 'Rajdhani', sans-serif; color:var(--head); text-shadow:0 0 22px rgba(0,229,255,.3); }
.sec p { margin:0; max-width:620px; color:var(--muted); font-size:14px; line-height:1.55; }

/* kpis */
.kpis { display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:14px; margin:6px 0 4px; }
.kpi { position:relative; border-radius:20px; padding:15px 18px 14px; overflow:hidden; border:1px solid var(--stroke);
  background:linear-gradient(150deg, rgba(255,255,255,.11), rgba(255,255,255,.02) 60%), var(--glass); -webkit-backdrop-filter:blur(18px); backdrop-filter:blur(18px);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.16), 0 18px 40px -26px var(--shadow); }
.kpi::after { content:""; position:absolute; right:-30px; top:-30px; width:110px; height:110px; border-radius:50%; background:radial-gradient(circle, color-mix(in srgb, var(--accent) 45%, transparent), transparent 70%); }
.kpi .lbl { font:500 11px 'JetBrains Mono', monospace; letter-spacing:.14em; text-transform:uppercase; color:var(--muted); position:relative; }
.kpi .val { font:700 40px/1.1 'Rajdhani', sans-serif; color:var(--head); margin-top:4px; text-shadow:0 0 20px color-mix(in srgb, var(--accent) 70%, transparent); position:relative; }
.kpi .val.long { font-size:26px; line-height:1.6; }
.kpi .sub { font-size:12px; color:var(--muted); margin-top:2px; position:relative; }

/* radar map */
.mapwrap { position:relative; padding:4px 4px 2px; }
.mapbox { position:relative; width:100%; aspect-ratio:830 / 475; border-radius:16px; background:radial-gradient(70% 80% at 40% 55%, rgba(0,229,255,.08), rgba(3,8,18,.55)); border:1px solid rgba(0,229,255,.14); }
.mapsvg { position:absolute; inset:0; width:100%; height:100%; border-radius:16px; }
.cn { position:absolute; width:20px; height:20px; border:2px solid var(--cyan); opacity:.8; z-index:3; pointer-events:none; }
.cn.a { left:-1px; top:-1px; border-right:0; border-bottom:0; border-top-left-radius:14px; } .cn.b { right:-1px; top:-1px; border-left:0; border-bottom:0; border-top-right-radius:14px; }
.cn.c { left:-1px; bottom:-1px; border-right:0; border-top:0; border-bottom-left-radius:14px; } .cn.d { right:-1px; bottom:-1px; border-left:0; border-top:0; border-bottom-right-radius:14px; }
.hud { position:absolute; top:12px; z-index:4; font:500 10.5px 'JetBrains Mono', monospace; letter-spacing:.18em; color:var(--cyan); opacity:.85; pointer-events:none; }
.hud.tl { left:18px; } .hud.tr { right:18px; }
.prov { stroke:rgba(0,229,255,.6); stroke-width:1.1; transition:fill .2s; } .prov:hover { fill:rgba(0,229,255,.34) !important; }
.plab { font:500 10px 'JetBrains Mono', monospace; fill:rgba(160,185,225,.65); letter-spacing:.16em; text-anchor:middle; pointer-events:none; }
.grat { stroke:rgba(0,229,255,.08); stroke-width:1; } .ringr { fill:none; stroke:rgba(0,229,255,.2); stroke-dasharray:3 7; }
.sweep { animation:sweep 8s linear infinite; } @keyframes sweep { to { transform:rotate(360deg); } }
.pin { position:absolute; width:0; height:0; z-index:5; outline:none; }
.pin:hover, .pin:focus-within { z-index:30; }
.pin .core, .pin .ring { position:absolute; width:var(--s); height:var(--s); left:calc(var(--s) / -2); top:calc(var(--s) / -2); border-radius:50%; }
.pin .core { background:radial-gradient(circle at 35% 30%, #fff, var(--c) 48%); box-shadow:0 0 12px var(--c), 0 0 30px color-mix(in srgb, var(--c) 55%, transparent); cursor:pointer; transition:transform .2s; }
.pin:hover .core { transform:scale(1.25); }
.pin .ring { border:2px solid var(--c); opacity:0; animation:ping var(--d) ease-out infinite; } .pin .ring.r2 { animation-delay:calc(var(--d) / 2); }
@keyframes ping { 0% { transform:scale(1); opacity:.95; } 100% { transform:scale(3.6); opacity:0; } }
.pin .lbl { position:absolute; left:calc(var(--s) / 2 + 7px); top:-8px; font:500 11px 'JetBrains Mono', monospace; color:var(--maptext); text-shadow:0 1px 8px var(--ringbg), 0 0 4px var(--ringbg); white-space:nowrap; pointer-events:none; }
.pin.right .lbl { left:auto; right:calc(var(--s) / 2 + 7px); }
.pin.nw .core { border-radius:6px; }
.tip { position:absolute; bottom:calc(var(--s) / 2 + 14px); left:0; width:310px; padding:12px 14px; border-radius:16px; opacity:0; visibility:hidden; transform:translate(-50%, 8px); transition:.18s; pointer-events:none;
  background:linear-gradient(150deg, rgba(255,255,255,.14), rgba(255,255,255,.03)), var(--tipbg); -webkit-backdrop-filter:blur(18px); backdrop-filter:blur(18px);
  border:1px solid color-mix(in srgb, var(--c) 60%, transparent); box-shadow:0 20px 50px -18px var(--shadow), 0 0 30px -10px var(--c); }
.pin.right .tip { transform:translate(-86%, 8px); } .pin.left .tip { transform:translate(-14%, 8px); }
.pin:hover .tip, .pin:focus-within .tip { opacity:1; visibility:visible; transform:translate(-50%, 0); }
.pin.right:hover .tip, .pin.right:focus-within .tip { transform:translate(-86%, 0); } .pin.left:hover .tip, .pin.left:focus-within .tip { transform:translate(-14%, 0); }
.tip-h { display:flex; flex-wrap:wrap; gap:2px 8px; align-items:baseline; margin-bottom:6px; } .tip-h b { color:var(--head); font:700 17px 'Rajdhani', sans-serif; letter-spacing:.04em; }
.tip-h em { font:400 11px 'JetBrains Mono', monospace; color:var(--muted); font-style:normal; } .tip-h span { margin-left:auto; font:600 11px 'JetBrains Mono', monospace; color:var(--c); }
.tip ul { margin:0; padding:0; list-style:none; } .tip li { font-size:12px; line-height:1.4; color:var(--body2); padding:5px 0; border-top:1px solid var(--line2); } .tip li.more { color:var(--muted); }
.maplegend { display:flex; flex-wrap:wrap; align-items:center; gap:8px; padding:12px 6px 4px; }

/* feed */
.feed-item { border-left:3px solid var(--c); background:rgba(255,255,255,.035); border-radius:0 12px 12px 0; padding:10px 12px; margin:0 0 10px; }
.feed-item .t { font-weight:600; color:var(--head); font-size:14px; line-height:1.35; }
.feed-item .m { font:400 11.5px 'JetBrains Mono', monospace; color:var(--muted); margin:3px 0 7px; }

/* story timeline */
.tl { position:relative; padding:6px 0 10px; }
.tl::before { content:""; position:absolute; left:50%; top:0; bottom:0; width:2px; margin-left:-1px; background:linear-gradient(180deg, transparent, var(--cyan) 5%, rgba(0,229,255,.25) 95%, transparent); box-shadow:0 0 14px rgba(0,229,255,.7); }
.tl-year { position:relative; text-align:center; margin:22px 0 16px; z-index:1; }
.tl-year span { display:inline-block; font:700 26px 'Rajdhani', sans-serif; letter-spacing:.1em; padding:3px 22px; border-radius:999px; color:var(--cyan); background:var(--yearbg); border:1px solid var(--cyan); box-shadow:0 0 22px rgba(0,229,255,.45); }
.tl-year em { display:block; font:400 11px 'JetBrains Mono', monospace; color:var(--muted); font-style:normal; margin-top:6px; }
.tl-item { position:relative; width:calc(50% - 38px); margin:0 0 20px; }
.tl-item.r { margin-left:calc(50% + 38px); }
.tl-dot { position:absolute; top:22px; width:14px; height:14px; border-radius:50%; background:var(--c); box-shadow:0 0 0 4px var(--ringbg), 0 0 18px var(--c); }
.tl-item.l .tl-dot { right:-45px; } .tl-item.r .tl-dot { left:-45px; }
.tl-item::after { content:""; position:absolute; top:28px; width:31px; height:1px; background:var(--c); opacity:.65; } .tl-item.l::after { right:-31px; } .tl-item.r::after { left:-31px; }
.tl-card { padding:16px 18px; border-radius:18px; border:1px solid color-mix(in srgb, var(--c) 40%, transparent);
  background:linear-gradient(150deg, rgba(255,255,255,.11), rgba(255,255,255,.02) 60%), var(--glass); -webkit-backdrop-filter:blur(16px); backdrop-filter:blur(16px);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.14), 0 18px 40px -26px var(--shadow), 0 0 30px -18px var(--c); transition:transform .2s, box-shadow .2s; }
.tl-card:hover { transform:translateY(-3px); box-shadow:inset 0 1px 0 rgba(255,255,255,.16), 0 22px 44px -24px var(--shadow), 0 0 36px -10px var(--c); }
.tl-date { font:500 11px 'JetBrains Mono', monospace; letter-spacing:.1em; color:color-mix(in srgb, var(--c) var(--chipk), #0b1b3a); text-transform:uppercase; }
.tl-card h4 { margin:5px 0 8px; font:700 21px/1.2 'Rajdhani', sans-serif; color:var(--head); } .tl-chips { display:flex; flex-wrap:wrap; gap:6px; }
.tl-card p { font-size:13.5px; line-height:1.6; color:var(--body2); margin:10px 0 8px; } .tl-foot { font:400 11.5px 'JetBrains Mono', monospace; color:var(--muted); }
.tl-foot a, .detail a { color:var(--cyan) !important; }
@media (max-width:900px) { .tl::before { left:18px; } .tl-year { text-align:left; padding-left:0; } .tl-item, .tl-item.r { width:auto; margin-left:46px; }
  .tl-item.l .tl-dot, .tl-item.r .tl-dot { left:-36px; right:auto; } .tl-item.l::after, .tl-item.r::after { left:-22px; right:auto; width:22px; } }

/* detail card */
.detail h3 { margin:0 0 4px; font-size:26px; color:var(--head); } .detail .summary { font-size:15px; line-height:1.6; margin:12px 0; }
.score-row { display:flex; justify-content:space-between; border-bottom:1px solid var(--line2); padding:5px 0; font-size:13px; } .score-row b { font-family:'JetBrains Mono', monospace; color:var(--cyan); }

/* native widgets on glass */
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"], [data-testid="stDateInput"] > div > div { background:var(--field) !important; border-color:var(--stroke) !important; border-radius:12px !important; }
[data-baseweb="tag"] { background:rgba(0,229,255,.16) !important; border-radius:8px !important; }
[data-testid="stWidgetLabel"] p { font:500 11px 'JetBrains Mono', monospace; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
[data-testid="stDataFrame"] { border:1px solid var(--stroke); border-radius:14px; overflow:hidden; }
.stDownloadButton button, .stButton button { border:1px solid var(--cyan); background:rgba(0,229,255,.08); color:var(--cyan); font-family:'JetBrains Mono', monospace; border-radius:12px; }
.stDownloadButton button:hover, .stButton button:hover { background:rgba(0,229,255,.2); border-color:var(--head); color:var(--head); }
[data-testid="stExpander"] { border:1px solid var(--stroke); border-radius:16px; background:rgba(255,255,255,.03); }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation:none !important; transition:none !important; scroll-behavior:auto !important; } }
</style>
"""

LIGHT_CSS = """
<style>
:root { --bg:#e9f0fb; --text:#10244a; --muted:#4f6590; --head:#0b1b3a; --body2:#30456d; --cyan:#00758f; --crimson:#c4102f; --blue:#2c5fd1;
  --glass:rgba(255,255,255,.62); --stroke:rgba(40,95,170,.24); --line2:rgba(15,40,90,.12); --navbg:rgba(243,248,255,.72); --tipbg:rgba(255,255,255,.93);
  --field:rgba(255,255,255,.85); --maptext:#10244a; --ringbg:rgba(233,240,251,.96); --yearbg:rgba(255,255,255,.95); --chipk:55%; --herop:#2b4068; --shadow:rgba(30,60,120,.35); }
.stApp::before { background:radial-gradient(40% 36% at 82% 8%, rgba(0,170,230,.24), transparent 70%), radial-gradient(38% 40% at 6% 30%, rgba(255,120,150,.22), transparent 70%),
  radial-gradient(44% 40% at 60% 96%, rgba(255,196,110,.34), transparent 70%); }
.stApp::after { background:linear-gradient(rgba(20,70,140,.05) 1px, transparent 1px) 0 0/48px 48px, linear-gradient(90deg, rgba(20,70,140,.05) 1px, transparent 1px) 0 0/48px 48px; }
[data-testid="stVerticalBlockBorderWrapper"], .kpi, .tl-card { background:linear-gradient(150deg, rgba(255,255,255,.85), rgba(255,255,255,.35) 60%), var(--glass); }
.feed-item, [data-testid="stExpander"] { background:rgba(255,255,255,.55); }
.callout { color:#6b4a00; background:rgba(255,194,51,.16); }
.nav-links a:hover { background:rgba(0,117,143,.12); }
.sec h2, .kpi .val { text-shadow:none; }

/* native text */
.stApp, [data-testid="stMarkdownContainer"] > p:not(.note), [data-testid="stMarkdownContainer"] li, [data-testid="stMarkdownContainer"] strong, [data-testid="stMarkdownContainer"] code { color:var(--text); }
[data-testid="stMarkdownContainer"] code { background:rgba(0,117,143,.10); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color:var(--muted) !important; }
input, textarea, [data-baseweb="select"] * { color:var(--text) !important; -webkit-text-fill-color:var(--text); opacity:1; }
input, textarea { background:transparent !important; }
input::placeholder { color:var(--muted) !important; -webkit-text-fill-color:var(--muted); opacity:.8; }
[data-testid="stDataFrame"] { filter:invert(.93) hue-rotate(180deg); }
[data-testid="stFileUploaderDropzone"] { background:var(--field); border-color:var(--stroke); } [data-testid="stFileUploaderDropzone"] * { color:var(--text) !important; }
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"] { color:var(--text) !important; }
[data-testid="stBaseButton-pills"] { background:rgba(255,255,255,.7) !important; border-color:var(--stroke) !important; }
[data-testid="stBaseButton-pillsActive"] { background:rgba(0,117,143,.16) !important; border-color:var(--cyan) !important; }
[data-testid="stBaseButton-pills"] *, [data-testid="stBaseButton-pillsActive"] * { color:var(--text) !important; }
[data-testid="stAlert"] * { color:inherit; }

/* hero turns to a Himalayan dawn */
.hero2 { background:linear-gradient(180deg, #a9cdf2 0%, #d9e8fb 42%, #ffe1d0 100%); box-shadow:0 30px 80px -40px rgba(30,80,160,.55), inset 0 1px 0 rgba(255,255,255,.7); }
.hero2 .aurora { background:radial-gradient(30% 30% at 72% 24%, rgba(255,196,120,.55), transparent 70%), radial-gradient(28% 30% at 20% 30%, rgba(255,120,150,.30), transparent 70%), radial-gradient(30% 24% at 50% 10%, rgba(120,160,255,.30), transparent 70%); }
.hero2 h1 { color:#0b1b3a; text-shadow:0 0 24px rgba(255,255,255,.7); } .hero2 .np { color:#b3122e; } .hero2 .eyebrow { color:#00667d; }
.stars { display:none; } .mf0 { stop-color:#86a9d6; } .mf1 { stop-color:#3d5f93; } .mm0 { stop-color:#4a6c9f; } .mm1 { stop-color:#2b4573; } .mt-near { fill:#17294a; }
.mt-far, .mt-mid { stroke:#ffffff; stroke-opacity:.55; } .snow { fill:#ffffff; opacity:1; } .pk-n { fill:#0b3f55; } .pk-h { fill:#2d5d78; }
.ticker { background:rgba(255,255,255,.62); } .tk { color:#1d3358; } .tk i { color:#7d93b8; }

/* radar map */
.mapbox { background:radial-gradient(70% 80% at 40% 55%, rgba(0,150,200,.10), rgba(255,255,255,.55)); border-color:rgba(0,117,143,.28); }
.prov { stroke:rgba(0,117,143,.75); } .prov:hover { fill:rgba(0,150,200,.30) !important; } .plab { fill:rgba(40,70,120,.75); }
.grat { stroke:rgba(0,90,140,.10); } .ringr { stroke:rgba(0,117,143,.28); }
.tip li, .tip-h em { color:var(--body2); }
</style>
"""


def inject(light: bool = False) -> None:
    st.markdown(CSS + (LIGHT_CSS if light else ""), unsafe_allow_html=True)


def chip(text: str, color: str | None = None) -> str:
    style = f' style="--c:{color}"' if color else ""
    return f'<span class="chip{"" if color else " plain"}"{style}>{html.escape(text)}</span>'


def kpi(label: str, value: str, sub: str, accent: str = CYAN) -> str:
    size = " long" if len(value) > 8 else ""
    return (f'<div class="kpi" style="--accent:{accent}"><div class="lbl">{html.escape(label)}</div>'
            f'<div class="val{size}">{html.escape(value)}</div><div class="sub">{html.escape(sub)}</div></div>')
