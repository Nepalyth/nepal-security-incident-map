"""Interactive 3D globe (canvas, no external libraries) in the spirit of a live cyber map.

It plots reported incidents as pulsing beacons around Nepal. It does not draw attack arcs: reports rarely say where an
attack came from, and inventing origins would be an unverified accusation.
"""

from __future__ import annotations

import base64
import json
from datetime import timedelta

import pandas as pd

from nepal_incident_map import data
from nepal_incident_map.geo import GAZETTEER
from nepal_incident_map.theme import CATEGORY_COLORS, SEVERITY_COLORS

NEPAL_CENTRE = (28.6, 83.9)  # where the "Nationwide" beacon sits, in the Himalaya
LIVE_COLOR = "#ffb020"

PALETTES = {
    False: {
        "ocean0": "#22508f", "ocean1": "#0d1f3b", "glow": "rgba(0,229,255,0.26)", "rim": "rgba(0,229,255,0.6)", "grat": "rgba(0,229,255,0.13)",
        "dot": "#86dcff", "nepalFill": "rgba(220,20,60,0.34)", "nepalLine": "#ff6b88", "fg": "#e4edff", "muted": "#9db0d2",
        "panel": "rgba(18,30,56,0.84)", "border": "rgba(150,215,255,0.30)", "accent": "#00e5ff", "ring": "#111c36",
    },
    True: {
        "ocean0": "#eaf4ff", "ocean1": "#a7c8ef", "glow": "rgba(0,117,143,0.20)", "rim": "rgba(0,90,130,0.55)", "grat": "rgba(0,70,120,0.15)",
        "dot": "#2d5d8f", "nepalFill": "rgba(220,20,60,0.28)", "nepalLine": "#c4102f", "fg": "#10244a", "muted": "#4f6590",
        "panel": "rgba(255,255,255,0.88)", "border": "rgba(40,95,170,0.30)", "accent": "#00758f", "ring": "#f4f8ff",
    },
}


def payload(frame: pd.DataFrame, light: bool) -> dict:
    """Everything the globe script needs, as plain JSON-safe values."""
    recent_cut = pd.Timestamp.today().normalize() - timedelta(days=30)
    places: dict[str, dict] = {}
    for row in frame.sort_values("date", ascending=False).itertuples():
        keys = [loc for loc in row.locations if loc in GAZETTEER] or ["Nationwide"]
        for loc in keys:
            lat, lon = (GAZETTEER[loc][0], GAZETTEER[loc][1]) if loc in GAZETTEER else NEPAL_CENTRE
            item = places.setdefault(loc, {"name": loc, "lat": lat, "lon": lon, "n": 0, "score": 0, "live": 0, "recent": 0, "lines": [], "nw": loc == "Nationwide"})
            item["n"] += 1
            item["score"] = max(item["score"], int(row.score))
            item["live"] += row.origin == "web"
            item["recent"] += row.date >= recent_cut
            item["lines"].append(f"{row.date:%d %b %Y} | {row.category} | {row.severity}: {row.title}")
    beacons = []
    for item in places.values():
        severity = "Unrated" if item["score"] <= 0 else data.severity_of(item["score"])
        beacons.append({**item, "lines": item["lines"][:5], "more": max(0, len(item["lines"]) - 5), "color": SEVERITY_COLORS[severity], "severity": severity})
    counts = frame["category"].value_counts()
    dots = data.load_world_dots()
    newest = frame.sort_values("date", ascending=False)
    top_score = int(frame["score"].max()) if len(frame) else 0
    top_sev = "Unrated" if top_score <= 0 else data.severity_of(top_score)
    hub = {
        "name": "Nepal", "lat": 27.9, "lon": 84.4, "n": len(frame), "live": int((frame["origin"] == "web").sum()), "recent": int((frame["date"] >= recent_cut).sum()),
        "lines": [f"{r.date:%d %b %Y} | {r.category} | {r.severity}: {r.title}" for r in newest.head(6).itertuples()], "more": max(0, len(frame) - 6),
        "color": SEVERITY_COLORS[top_sev], "severity": top_sev, "nw": False,
    }
    return {
        "palette": PALETTES[light], "beacons": beacons, "hub": hub, "liveColor": LIVE_COLOR, "total": len(frame), "live": hub["live"],
        "counters": [{"name": c, "n": int(n), "color": CATEGORY_COLORS[c]} for c, n in counts.items()],
        "severities": [{"name": s, "color": c} for s, c in SEVERITY_COLORS.items()],
        "coarse": dots["coarse"], "fine": dots["fine"],
        "nepal": [ring for rings in data.load_provinces().values() for ring in rings],
        "tlon": 84.2, "tlat": 25.0,
    }


def globe_html(frame: pd.DataFrame, light: bool = False) -> str:
    body = json.dumps(payload(frame, light), separators=(",", ":")).replace("</", "<\\/").replace("<!--", "<\\u0021--")
    return _TEMPLATE.replace("__DATA__", body)


def globe_src(frame: pd.DataFrame, light: bool = False) -> str:
    """The globe as a data: URL, so its script runs in an opaque origin with no access to the Streamlit page."""
    return "data:text/html;charset=utf-8;base64," + base64.b64encode(globe_html(frame, light).encode()).decode()


_TEMPLATE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
html,body{margin:0;height:100%;background:transparent;overflow:hidden;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:var(--fg)}
#wrap{position:relative;width:100%;height:100%}
canvas{display:block;width:100%;height:100%;cursor:grab;touch-action:none}
canvas.drag{cursor:grabbing}
.hud{position:absolute;font-size:10.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--accent);pointer-events:none}
.panel{position:absolute;background:var(--panel);border:1px solid var(--border);border-radius:14px;padding:10px 12px;backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px)}
#counters{right:10px;top:34px;min-width:176px;pointer-events:none}
#counters h4{margin:0 0 6px;font-size:10px;letter-spacing:.18em;color:var(--muted);font-weight:600}
.row{display:flex;align-items:center;gap:8px;font-size:12px;line-height:1.7}.row i{width:8px;height:8px;border-radius:50%;flex:none}.row b{margin-left:auto;font-weight:700}
#legend{left:10px;bottom:10px;display:flex;flex-wrap:wrap;gap:4px 12px;max-width:62%;font-size:10.5px;color:var(--muted);pointer-events:none}
#legend span{display:flex;align-items:center;gap:5px}#legend i{width:8px;height:8px;border-radius:50%}
#ctrls{right:10px;bottom:10px;display:flex;gap:6px;padding:6px}
button{font:600 10.5px ui-monospace,monospace;letter-spacing:.1em;text-transform:uppercase;color:var(--accent);background:transparent;border:1px solid var(--accent);border-radius:9px;padding:6px 9px;cursor:pointer}
button:hover,button.on{background:color-mix(in srgb,var(--accent) 18%,transparent)}
#tip{position:absolute;display:none;max-width:320px;pointer-events:none;z-index:5}
#tip b{display:block;font-size:14px;margin-bottom:4px}#tip em{font-style:normal;color:var(--muted);font-size:11px}#tip div{font-size:11.5px;line-height:1.4;padding:4px 0;border-top:1px solid var(--border)}
#live{left:50%;transform:translateX(-50%);top:10px;color:#ffb020}
</style></head><body><div id="wrap"><canvas id="cv"></canvas>
<div class="hud" style="left:14px;top:12px">NEPAL // CYBER GLOBE</div><div class="hud" id="live"></div><div class="hud" style="right:14px;top:12px;color:var(--muted)">DRAG TO ROTATE</div>
<div class="panel" id="counters"><h4>SIGNALS IN VIEW</h4><div id="rows"></div></div>
<div class="panel" id="legend"></div>
<div class="panel" id="ctrls"><button id="bFocus" class="on">Globe</button><button id="bNepal">Nepal</button><button id="bSpin">Spin</button><button id="bIn">+</button><button id="bOut">&minus;</button></div>
<div class="panel" id="tip"></div></div>
<script>
const D=__DATA__,P=D.palette,root=document.documentElement;
root.style.setProperty('--fg',P.fg);root.style.setProperty('--muted',P.muted);root.style.setProperty('--accent',P.accent);root.style.setProperty('--panel',P.panel);root.style.setProperty('--border',P.border);
const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
const still=matchMedia('(prefers-reduced-motion: reduce)').matches,rad=Math.PI/180;
let W=0,H=0;
function resize(){const r=cv.getBoundingClientRect(),d=Math.min(devicePixelRatio||1,2);W=r.width;H=r.height;cv.width=W*d;cv.height=H*d;ctx.setTransform(d,0,0,d,0,0)}
new ResizeObserver(resize).observe(cv);resize();
const S={lon:-40,lat:14,zoom:1.05,tz:1.25,mode:'focus',drag:null,hover:null,visible:true};
if(still){S.lon=D.tlon;S.lat=D.tlat;S.zoom=S.tz}
const base=()=>Math.min(W,H)*0.40,radius=()=>base()*S.zoom;
function proj(lo,la){const l=(lo-S.lon)*rad,f=la*rad,f0=S.lat*rad,R=radius();
 return{x:W/2+R*Math.cos(f)*Math.sin(l),y:H/2-R*(Math.cos(f0)*Math.sin(f)-Math.sin(f0)*Math.cos(f)*Math.cos(l)),c:Math.sin(f0)*Math.sin(f)+Math.cos(f0)*Math.cos(f)*Math.cos(l)}}
function polyline(pts){ctx.beginPath();let pen=false;for(const q of pts){const p=proj(q[0],q[1]);if(p.c>0){pen?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y);pen=true}else pen=false}ctx.stroke()}
function sphere(){const R=radius(),cx=W/2,cy=H/2;let g=ctx.createRadialGradient(cx,cy,R*.92,cx,cy,R*1.3);g.addColorStop(0,P.glow);g.addColorStop(1,'rgba(0,0,0,0)');
 ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R*1.3,0,7);ctx.fill();
 g=ctx.createRadialGradient(cx-R*.35,cy-R*.4,R*.1,cx,cy,R);g.addColorStop(0,P.ocean0);g.addColorStop(1,P.ocean1);ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R,0,7);ctx.fill();
 ctx.strokeStyle=P.rim;ctx.lineWidth=1.2;ctx.stroke();
 ctx.strokeStyle=P.grat;ctx.lineWidth=.8;
 for(let lo=-180;lo<180;lo+=20){const a=[];for(let la=-90;la<=90;la+=4)a.push([lo,la]);polyline(a)}
 for(let la=-80;la<=80;la+=20){const a=[];for(let lo=-180;lo<=180;lo+=4)a.push([lo,la]);polyline(a)}}
function land(list,size){ctx.fillStyle=P.dot;for(const q of list){const p=proj(q[0],q[1]);if(p.c>0.02){ctx.globalAlpha=.18+.7*Math.min(1,p.c*1.4);ctx.fillRect(p.x-size/2,p.y-size/2,size,size)}}ctx.globalAlpha=1}
function nepal(){ctx.lineWidth=1.3;ctx.strokeStyle=P.nepalLine;ctx.fillStyle=P.nepalFill;
 for(const ring of D.nepal){const pts=ring.map(q=>proj(q[0],q[1]));if(pts.some(p=>p.c<=0.02))continue;ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();ctx.fill();ctx.stroke()}}
let drawn=[];
function beacons(t){drawn=[];const z=Math.min(S.zoom,2),items=S.zoom<2.2?[D.hub]:D.beacons,boxes=[];
 for(const b of items){const p=proj(b.lon,b.lat);if(p.c<.1)continue;const size=(4.5+Math.sqrt(b.n)*(items.length===1?1.5:2))*Math.pow(z,.45),speed=b.recent?.7:.35,
  fade=Math.min(1,p.c*2);
  if(!still)for(let k=0;k<2;k++){const ph=((t*speed+b.lon*.013+k*.5)%1);ctx.globalAlpha=(1-ph)*.85*fade;ctx.strokeStyle=b.live?D.liveColor:b.color;ctx.lineWidth=1.6;ctx.beginPath();ctx.arc(p.x,p.y,size*(1+ph*3.4),0,7);ctx.stroke()}
  ctx.globalAlpha=fade;ctx.shadowColor=b.color;ctx.shadowBlur=16;const g=ctx.createRadialGradient(p.x-size*.3,p.y-size*.3,1,p.x,p.y,size);g.addColorStop(0,'#fff');g.addColorStop(.5,b.color);g.addColorStop(1,b.color);
  ctx.fillStyle=g;ctx.beginPath();if(b.nw){ctx.rect(p.x-size,p.y-size,size*2,size*2)}else{ctx.arc(p.x,p.y,size,0,7)}ctx.fill();ctx.shadowBlur=0;
  if(b.live){ctx.strokeStyle=D.liveColor;ctx.lineWidth=2;ctx.setLineDash([3,3]);ctx.beginPath();ctx.arc(p.x,p.y,size+4,0,7);ctx.stroke();ctx.setLineDash([])}
  ctx.globalAlpha=1;
  if(S.zoom>1.15||S.hover===b){ctx.font='600 11px ui-monospace,monospace';const label=items.length===1?'NEPAL  '+b.n:b.name,w=ctx.measureText(label).width,box=[p.x+size+7,p.y-6,w,14];
   if(S.hover===b||!boxes.some(q=>box[0]<q[0]+q[2]&&box[0]+box[2]>q[0]&&box[1]<q[1]+q[3]&&box[1]+box[3]>q[1])){boxes.push(box);ctx.fillStyle=P.fg;ctx.shadowColor=P.ring;ctx.shadowBlur=6;ctx.fillText(label,box[0],p.y+4);ctx.shadowBlur=0}}
  drawn.push({b,x:p.x,y:p.y,r:Math.max(12,size+6)})}}
let last=performance.now();
function frame(now){const t=now/1000,dt=Math.min(.05,(now-last)/1000);last=now;
 if(S.visible){
  if(!S.drag&&!still){const k=Math.min(1,dt*2.4);
   if(S.mode==='focus'){let d=((D.tlon-S.lon+540)%360)-180;S.lon+=d*k+Math.sin(t*.35)*.015;S.lat+=((S.tz>2.5?28:D.tlat)-S.lat)*k;S.zoom+=(S.tz-S.zoom)*k}
   else if(S.mode==='spin'){S.lon+=dt*9;S.lat+=(18-S.lat)*k;S.zoom+=(S.tz-S.zoom)*k}
   else{S.lon+=dt*4;S.lat+=(16-S.lat)*k;S.zoom+=(S.tz-S.zoom)*k}}
  ctx.clearRect(0,0,W,H);sphere();land(D.coarse,1.5+.5*S.zoom);if(S.zoom>1.7)land(D.fine,2.2);nepal();beacons(t)}
 requestAnimationFrame(frame)}
requestAnimationFrame(frame);
new IntersectionObserver(e=>{S.visible=e[0].isIntersecting}).observe(cv);
// interaction
function setMode(m,z){S.mode=m;S.tz=z;for(const [id,mm,zz] of [['bFocus','focus',1.25],['bNepal','focus',6.5],['bSpin','spin',0]])document.getElementById(id).classList.toggle('on',mm===m&&(zz===0||zz===z))}
document.getElementById('bFocus').onclick=()=>setMode('focus',1.25);document.getElementById('bNepal').onclick=()=>setMode('focus',6.5);
document.getElementById('bSpin').onclick=()=>setMode('spin',1.15);
document.getElementById('bIn').onclick=()=>{S.tz=Math.min(12,S.zoom*1.5);S.zoom=S.tz};document.getElementById('bOut').onclick=()=>{S.tz=Math.max(.9,S.zoom/1.5);S.zoom=S.tz};
cv.addEventListener('pointerdown',e=>{cv.setPointerCapture(e.pointerId);S.drag={x:e.clientX,y:e.clientY,moved:false};cv.classList.add('drag');S.mode='manual';for(const id of['bFocus','bNepal','bSpin'])document.getElementById(id).classList.remove('on')});
cv.addEventListener('pointermove',e=>{
 if(S.drag){const dx=e.clientX-S.drag.x,dy=e.clientY-S.drag.y;if(Math.abs(dx)+Math.abs(dy)>2)S.drag.moved=true;const k=1/radius()/rad;S.lon-=dx*k;S.lat=Math.max(-80,Math.min(80,S.lat+dy*k));S.drag.x=e.clientX;S.drag.y=e.clientY;S.tz=S.zoom;tip.style.display='none';return}
 hit(e)});
cv.addEventListener('pointerup',e=>{const moved=S.drag&&S.drag.moved;S.drag=null;cv.classList.remove('drag');if(!moved)hit(e)});
cv.addEventListener('pointerleave',()=>{if(!S.drag){tip.style.display='none';S.hover=null}});
cv.addEventListener('wheel',e=>{if(e.ctrlKey||e.metaKey){e.preventDefault();S.zoom=Math.max(.9,Math.min(12,S.zoom*Math.exp(-e.deltaY*.002)));S.tz=S.zoom}},{passive:false});
function hit(e){const r=cv.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;let best=null,bd=1e9;
 for(const d of drawn){const dd=Math.hypot(d.x-x,d.y-y);if(dd<d.r&&dd<bd){best=d;bd=dd}}
 S.hover=best?best.b:null;if(!best){tip.style.display='none';return}
 const b=best.b;tip.replaceChildren();const h=document.createElement('b');h.textContent=b.name;tip.appendChild(h);
 const em=document.createElement('em');em.textContent=b.n+' incident'+(b.n===1?'':'s')+(b.live?' ('+b.live+' live web, unreviewed)':'')+' | worst: '+b.severity;tip.appendChild(em);
 for(const l of b.lines){const d=document.createElement('div');d.textContent=l;tip.appendChild(d)}
 if(b.more){const d=document.createElement('div');d.textContent='+'+b.more+' more';tip.appendChild(d)}
 tip.style.borderColor=b.color;tip.style.display='block';const tw=tip.offsetWidth,th=tip.offsetHeight;
 tip.style.left=Math.max(8,Math.min(W-tw-8,x-tw/2))+'px';tip.style.top=Math.max(8,y-th-18<8?y+20:y-th-18)+'px'}
// static HUD
const rows=document.getElementById('rows');
if(!D.counters.length){rows.textContent='No incidents in view'}
for(const c of D.counters){const r=document.createElement('div');r.className='row';const i=document.createElement('i');i.style.background=c.color;const n=document.createElement('span');n.textContent=c.name;const v=document.createElement('b');v.textContent=c.n;r.append(i,n,v);rows.appendChild(r)}
const lg=document.getElementById('legend');
for(const s of D.severities){const sp=document.createElement('span');const i=document.createElement('i');i.style.background=s.color;sp.append(i,document.createTextNode(s.name));lg.appendChild(sp)}
{const sp=document.createElement('span');const i=document.createElement('i');i.style.border='2px dashed '+D.liveColor;i.style.background='transparent';sp.append(i,document.createTextNode('live web, unreviewed'));lg.appendChild(sp)}
if(D.live){document.getElementById('live').textContent='LIVE WEB: '+D.live+' UNREVIEWED'}
</script></body></html>"""
