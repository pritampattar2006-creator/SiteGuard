"""SiteGuard design system: the look of the three pages and the small HTML components they share.

Industrial-safety identity: warm paper background, hazard-stripe accents, safety orange, condensed headline type,
challan-style case tickets and lanyard ID cards. Components return HTML strings so pages stay short.
"""
from __future__ import annotations

import base64
import html
from datetime import date
from pathlib import Path

import streamlit as st

INK, ORANGE, YELLOW, PAPER, CARD, LINE = "#12202b", "#ff6a13", "#ffc400", "#f5f1e8", "#fffdf8", "#e4dccb"
GOOD, WARN, BAD, BLUE, GREY = "#1f8a5b", "#d98a00", "#d1332e", "#2b6cb0", "#6b7580"

STATUS_COLOUR = {"Open": BAD, "Disputed": WARN, "Acknowledged": BLUE, "Resolved": GOOD, "Dismissed": GREY}
STATE_STYLE = {  # PPE item state -> (symbol, colour)
    "PRESENT": ("&#10003;", GOOD), "MISSING": ("&#10007;", BAD), "UNVERIFIABLE": ("?", WARN), "NOT_REQUIRED": ("&ndash;", GREY),
}

WEIGHT_CANDIDATES = ["weights/best.pt", "weights/best_v2.pt", "weights/best_v1.pt"]
EXTRA_CANDIDATES = ["weights/extras.pt"]


def find_weights() -> str:
    return next((p for p in WEIGHT_CANDIDATES if Path(p).exists()), WEIGHT_CANDIDATES[0])


def find_extra_weights() -> str | None:
    return next((p for p in EXTRA_CANDIDATES if Path(p).exists()), None)


@st.cache_resource
def load_detector(weights: str, extras: str | None = None, best: bool = False):
    from .detector import Detector

    return Detector(weights, extra_weights=extras, augment=best, ensemble=best)


@st.cache_data(show_spinner=False)
def img_uri(path: str, width: int = 520, mtime: float = 0.0) -> str:
    """A small inline copy of an image file, so custom HTML cards can show evidence photos."""
    import cv2

    image = cv2.imread(path)
    if image is None:
        return ""
    h, w = image.shape[:2]
    if w > width:
        image = cv2.resize(image, (width, int(h * width / w)))
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return "data:image/jpeg;base64," + base64.b64encode(buffer).decode() if ok else ""


def photo(path: str, width: int = 520) -> str:
    return img_uri(path, width, Path(path).stat().st_mtime) if path and Path(path).exists() else ""


CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&family=JetBrains+Mono:wght@500&display=swap');
html, body, [class*="st-"], .stMarkdown {{ font-family: 'Barlow', system-ui, 'Segoe UI', sans-serif; }}
.block-container {{ padding-top: 1.2rem; padding-bottom: 3rem; max-width: 1320px; }}
h1, h2, h3, h4 {{ font-family: 'Barlow Condensed', 'Arial Narrow', sans-serif; letter-spacing: .01em; color: {INK}; }}
h3 {{ text-transform: uppercase; font-size: 1.25rem !important; }}
[data-testid="stSidebar"] {{ border-right: 1px solid {LINE}; }}
[data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {INK}; border-radius: 8px; }}
[data-testid="stSidebarNav"] a[aria-current="page"] * {{ color: #fff !important; }}
[data-testid="stSidebarNav"] a {{ border-radius: 8px; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; border-bottom: 2px solid {LINE}; }}
.stTabs [data-baseweb="tab"] {{ font-family: 'Barlow Condensed'; font-size: 1.1rem; text-transform: uppercase; letter-spacing: .04em; }}
[data-testid="stExpander"] {{ background: {CARD}; border: 1px solid {LINE}; border-radius: 12px; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ background: {CARD}; }}
.brand {{ display:flex; align-items:center; gap:10px; padding: 4px 0 10px; }}
.brand .logo {{ width:38px; height:38px; background:{INK}; border-radius:9px; display:flex; align-items:center; justify-content:center;
                border-bottom: 5px solid {YELLOW}; box-sizing:border-box; }}
.brand b {{ font-family:'Barlow Condensed'; font-size:1.45rem; letter-spacing:.04em; color:{INK}; line-height:1; }}
.brand span {{ display:block; font-size:.72rem; color:{GREY}; letter-spacing:.08em; text-transform:uppercase; }}

.hero {{ position:relative; background:{INK}; color:#fff; border-radius:16px; padding:26px 30px 22px; margin-bottom:20px; overflow:hidden;
         background-image: linear-gradient(rgba(255,255,255,.045) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.045) 1px, transparent 1px);
         background-size: 30px 30px; }}
.hero:before {{ content:''; position:absolute; left:0; right:0; top:0; height:9px;
                background: repeating-linear-gradient(135deg, {YELLOW} 0 14px, {INK} 14px 28px); }}
.hero .eyebrow {{ color:{YELLOW}; font-size:.78rem; letter-spacing:.18em; text-transform:uppercase; font-weight:600; margin-top:6px; }}
.hero h1 {{ color:#fff; margin:.1rem 0 .2rem; font-size:2.5rem; text-transform:uppercase; line-height:1.05; }}
.hero p {{ margin:0; color:#c8d0d6; max-width:760px; }}
.hero .chips {{ margin-top:14px; display:flex; flex-wrap:wrap; gap:8px; }}
.hero .chips span {{ background:rgba(255,255,255,.09); border:1px solid rgba(255,255,255,.16); padding:3px 12px; border-radius:999px; font-size:.82rem; color:#eef1f3; }}

.tile {{ position:relative; background:{CARD}; border:1px solid {LINE}; border-radius:14px; padding:14px 16px 12px 20px; overflow:hidden; height:100%; }}
.tile:before {{ content:''; position:absolute; left:0; top:0; bottom:0; width:6px; background:var(--c, {INK}); }}
.tile .l {{ font-size:.74rem; text-transform:uppercase; letter-spacing:.09em; color:{GREY}; font-weight:600; }}
.tile .v {{ font-family:'Barlow Condensed'; font-size:2.6rem; font-weight:700; color:{INK}; line-height:1.05; }}
.tile .s {{ font-size:.8rem; color:{GREY}; min-height:1.1em; }}
.tile svg.spark {{ position:absolute; right:12px; bottom:12px; opacity:.9; }}

.sec {{ display:flex; align-items:baseline; gap:12px; margin: 26px 0 10px; }}
.sec h3 {{ margin:0; padding:0; }} .sec:before {{ content:''; width:7px; height:22px; background:{ORANGE}; border-radius:2px; align-self:center; }}
.sec span {{ color:{GREY}; font-size:.9rem; }}

.pill {{ display:inline-flex; align-items:center; gap:6px; padding:2px 11px 2px 4px; border-radius:999px; font-size:.82rem; font-weight:600;
         border:1px solid var(--c); color:var(--c); background:#fff; margin:2px 4px 2px 0; }}
.pill i {{ font-style:normal; width:19px; height:19px; border-radius:50%; background:var(--c); color:#fff; display:inline-flex; align-items:center; justify-content:center; font-size:.75rem; }}
.chip {{ display:inline-block; padding:2px 11px; border-radius:999px; font-size:.76rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color:#fff; background:var(--c); }}
.chip.soft {{ background:color-mix(in srgb, var(--c) 14%, white); color:var(--c); }}
.demo {{ background:#ede4ff; color:#5b34a8; }}

.worker {{ background:{CARD}; border:1px solid {LINE}; border-left:7px solid var(--c); border-radius:12px; padding:11px 14px; margin-bottom:9px; }}
.worker .top {{ display:flex; justify-content:space-between; align-items:center; }}
.worker .name {{ font-family:'Barlow Condensed'; font-size:1.25rem; font-weight:700; text-transform:uppercase; }}
.worker .why {{ color:{GREY}; font-size:.86rem; margin-top:3px; }}

.ticket {{ display:flex; background:{CARD}; border:1px solid {LINE}; border-radius:14px; margin-bottom:14px; overflow:hidden; position:relative; }}
.ticket .stub {{ width:128px; flex:none; background:{INK}; color:#fff; padding:14px 10px; text-align:center; display:flex; flex-direction:column; justify-content:center; gap:5px; }}
.ticket .stub small {{ color:{YELLOW}; letter-spacing:.2em; font-size:.68rem; }}
.ticket .stub .no {{ font-family:'JetBrains Mono'; font-size:1.25rem; letter-spacing:.04em; }}
.ticket .perf {{ width:0; border-left:2px dashed #b9ae95; position:relative; margin:10px 0; }}
.ticket .perf:before, .ticket .perf:after {{ content:''; position:absolute; left:-12px; width:22px; height:22px; border-radius:50%; background:{PAPER}; border:1px solid {LINE}; }}
.ticket .perf:before {{ top:-22px; }} .ticket .perf:after {{ bottom:-22px; }}
.ticket .body {{ flex:1; padding:14px 18px; min-width:0; }}
.ticket .what {{ font-family:'Barlow Condensed'; font-size:1.6rem; font-weight:700; text-transform:uppercase; color:{BAD}; line-height:1.1; }}
.ticket .meta {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(140px, 1fr)); gap:6px 16px; margin:8px 0; font-size:.86rem; }}
.ticket .meta b {{ display:block; font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; color:{GREY}; font-weight:600; }}
.ticket .why {{ color:#3b4a56; font-size:.9rem; }}
.ticket img {{ width:150px; flex:none; object-fit:cover; border-left:1px solid {LINE}; }}
@media (max-width: 800px) {{ .ticket {{ flex-direction:column; }} .ticket .perf {{ display:none; }} .ticket img {{ width:100%; max-height:220px; }} }}

.idcard {{ position:relative; background:{CARD}; border:1px solid {LINE}; border-radius:18px; padding:20px 22px 18px; overflow:hidden; display:flex; gap:18px; align-items:center; flex-wrap:wrap; }}
.idcard:before {{ content:''; position:absolute; left:0; right:0; top:0; height:12px; background: repeating-linear-gradient(135deg, {YELLOW} 0 14px, {INK} 14px 28px); }}
.idcard .avatar {{ width:84px; height:84px; border-radius:50%; background:{INK}; color:{YELLOW}; font-family:'Barlow Condensed'; font-weight:700; font-size:2.3rem;
                   display:flex; align-items:center; justify-content:center; border:4px solid {ORANGE}; margin-top:10px; }}
.idcard .who {{ flex:1; min-width:200px; margin-top:10px; }}
.idcard .who h2 {{ margin:0; font-size:2.1rem; text-transform:uppercase; line-height:1.05; }}
.idcard .who .id {{ font-family:'JetBrains Mono'; color:{GREY}; font-size:.92rem; }}
.idcard .barcode {{ height:26px; width:170px; margin-top:8px; background: repeating-linear-gradient(90deg, {INK} 0 2px, transparent 2px 5px, {INK} 5px 6px, transparent 6px 10px, {INK} 10px 13px, transparent 13px 15px); opacity:.8; }}
.idcard .score {{ margin-top:10px; text-align:center; }}

.badge {{ display:inline-flex; align-items:center; gap:8px; background:#fff7e0; border:1px solid {YELLOW}; border-radius:12px; padding:6px 12px; margin:0 8px 8px 0; }}
.badge b {{ font-family:'Barlow Condensed'; font-size:1.05rem; text-transform:uppercase; }} .badge span {{ color:{GREY}; font-size:.8rem; }}

.cal {{ display:flex; gap:4px; }} .cal .col {{ display:flex; flex-direction:column; gap:4px; }}
.cal .d {{ width:17px; height:17px; border-radius:4px; background:#e8e1d0; }}
.cal .d.f {{ background:transparent; }} .cal .d.n1 {{ background:#ffb27a; }} .cal .d.n2 {{ background:{ORANGE}; }} .cal .d.n3 {{ background:{BAD}; }}
.cal-legend {{ color:{GREY}; font-size:.78rem; margin-top:6px; }}

.feed {{ border-left:3px solid {LINE}; padding-left:14px; }}
.feed .it {{ position:relative; margin-bottom:12px; font-size:.9rem; }}
.feed .it:before {{ content:''; position:absolute; left:-21px; top:5px; width:11px; height:11px; border-radius:50%; background:var(--c, {ORANGE}); border:2px solid {PAPER}; }}
.feed .it small {{ color:{GREY}; display:block; }}
.tl {{ border-left:3px solid {LINE}; margin:2px 0 2px 6px; padding:1px 0 1px 12px; font-size:.88rem; }} .tl b {{ color:{INK}; }}
.muted {{ color:{GREY}; font-size:.88rem; }}
.tip {{ background:#fff7e0; border-left:5px solid {YELLOW}; border-radius:8px; padding:10px 14px; margin-bottom:8px; font-size:.92rem; }}
.callout {{ background:{INK}; color:#fff; border-radius:12px; padding:12px 18px; margin-bottom:12px; border-left:8px solid {ORANGE}; }}
.callout b {{ color:{YELLOW}; }}
.insight {{ background:{CARD}; border:1px solid {LINE}; border-radius:12px; padding:9px 14px; margin-bottom:7px; font-size:.93rem; }}
.insight:before {{ content:'\\25B8'; color:{ORANGE}; margin-right:8px; font-weight:700; }}
</style>
"""

LOGO = f'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="{YELLOW}" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M8.5 12l2.5 2.5 4.5-5"/></svg>'


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def brand() -> None:
    st.markdown(f'<div class="brand"><div class="logo">{LOGO}</div><div><b>SITEGUARD</b><span>PPE safety desk</span></div></div>', unsafe_allow_html=True)


def esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def hero(eyebrow: str, title: str, subtitle: str, chips: list[str] | None = None) -> None:
    chip_html = "".join(f"<span>{esc(c)}</span>" for c in chips or [])
    st.markdown(f'<div class="hero"><div class="eyebrow">{esc(eyebrow)}</div><h1>{esc(title)}</h1><p>{esc(subtitle)}</p>'
                f'<div class="chips">{chip_html}</div></div>', unsafe_allow_html=True)


def section(title: str, sub: str = "") -> None:
    st.markdown(f'<div class="sec"><h3>{esc(title)}</h3><span>{esc(sub)}</span></div>', unsafe_allow_html=True)


def spark(series: list[int], colour: str = ORANGE, width: int = 96, height: int = 34) -> str:
    """A tiny trend line."""
    if len(series) < 2:
        return ""
    top = max(series) or 1
    pts = [(i * (width - 4) / (len(series) - 1) + 2, height - 4 - (v / top) * (height - 10)) for i, v in enumerate(series)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (f'<svg class="spark" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><polyline points="{line}" fill="none" '
            f'stroke="{colour}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/><circle cx="{pts[-1][0]:.1f}" cy="{pts[-1][1]:.1f}" r="3.2" fill="{colour}"/></svg>')


def tile(label: str, value, sub: str = "", colour: str = INK, series: list[int] | None = None) -> str:
    return (f'<div class="tile" style="--c:{colour}"><div class="l">{esc(label)}</div><div class="v">{esc(value)}</div>'
            f'<div class="s">{esc(sub)}</div>{spark(series or [], colour)}</div>')


def tiles(items: list[tuple]) -> None:
    """items: (label, value, sub, colour, series)"""
    for col, item in zip(st.columns(len(items)), items):
        col.markdown(tile(*item), unsafe_allow_html=True)


def ring(value: int | None, label: str, colour: str = ORANGE, size: int = 130) -> str:
    """A circular gauge, 0-100."""
    radius, stroke = size / 2 - 11, 11
    circumference = 2 * 3.14159 * radius
    filled = circumference * (0 if value is None else max(0, min(value, 100))) / 100
    text = "&ndash;" if value is None else str(value)
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}"><circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="#e8e1d0" stroke-width="{stroke}"/>'
            f'<circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="{colour}" stroke-width="{stroke}" stroke-linecap="round" '
            f'stroke-dasharray="{filled:.1f} {circumference:.1f}" transform="rotate(-90 {size/2} {size/2})"/>'
            f'<text x="50%" y="48%" text-anchor="middle" dominant-baseline="middle" font-family="Barlow Condensed" font-size="{size*0.34:.0f}" font-weight="700" fill="{INK}">{text}</text>'
            f'<text x="50%" y="72%" text-anchor="middle" font-family="Barlow" font-size="{size*0.095:.0f}" fill="{GREY}" letter-spacing="1">{esc(label.upper())}</text></svg>')


def chip(status: str) -> str:
    return f'<span class="chip" style="--c:{STATUS_COLOUR.get(status, GREY)}">{esc(status)}</span>'


def demo_chip() -> str:
    return '<span class="chip demo">Demo data</span>'


def ppe_pills(states: dict[str, str]) -> str:
    """One pill per checked item: tick, cross or question mark."""
    from .types import ITEM_NAMES, ITEMS

    out = []
    for item in ITEMS:
        state = states.get(item, "NOT_REQUIRED")
        if state == "NOT_REQUIRED":
            continue
        symbol, colour = STATE_STYLE[state]
        out.append(f'<span class="pill" style="--c:{colour}"><i>{symbol}</i>{ITEM_NAMES[item]}</span>')
    return "".join(out)


def worker_card(verdict) -> str:
    colour = {"COMPLIANT": GOOD, "VIOLATION": BAD, "NEEDS_REVIEW": WARN}[verdict.status]
    word = {"COMPLIANT": "Compliant", "VIOLATION": "Violation", "NEEDS_REVIEW": "Needs review"}[verdict.status]
    states = verdict.states or {"helmet": verdict.helmet_state, "vest": verdict.vest_state}
    return (f'<div class="worker" style="--c:{colour}"><div class="top"><span class="name">Worker {verdict.worker_id}</span>'
            f'<span class="chip" style="--c:{colour}">{word}</span></div><div>{ppe_pills(states)}</div>'
            f'<div class="why">{esc(verdict.reason)}</div></div>')


def ticket(record, states: dict[str, str] | None = None) -> str:
    """A violation shown as a challan: stub with the case number, perforation, details, evidence photo."""
    src = photo(record["crop_path"] or record["evidence_path"], 360)
    who = record["worker_name"] or f"Unassigned ({record['worker_ref']})"
    where = record["location"] or "Not set"
    source = record["source_name"] or record["source"]
    if record["video_time_s"] is not None:
        source += f" at {record['video_time_s']:.1f} s"
    image = f'<img src="{src}">' if src else ""
    return (f'<div class="ticket"><div class="stub"><small>CASE</small><div class="no">#{record["id"]:05d}</div>{chip(record["status"])}</div>'
            f'<div class="perf"></div><div class="body"><div class="what">{esc(record["missing"])}</div>'
            f'<div class="meta"><div><b>Worker</b>{esc(who)}</div><div><b>When</b>{esc(pretty_time(record["occurred_at"]))}</div>'
            f'<div><b>Location</b>{esc(where)}</div><div><b>Source</b>{esc(source)}</div></div>'
            f'<div class="why">{esc(record["reason"])}</div></div>{image}</div>')


def calendar(weeks) -> str:
    """GitHub-style activity grid: one square per day, darker means more violations."""
    today = date.today()
    cols = []
    for week in weeks:
        cells = "".join(f'<div class="d {"f" if d > today else "n3" if n >= 3 else "n2" if n == 2 else "n1" if n == 1 else ""}" title="{d:%d %b}: {n}"></div>' for d, n in week)
        cols.append(f'<div class="col">{cells}</div>')
    return f'<div class="cal">{"".join(cols)}</div><div class="cal-legend">Last {len(weeks)} weeks &middot; each square is a day &middot; darker = more violations</div>'


def badge(title: str, why: str) -> str:
    return f'<div class="badge"><svg width="22" height="22" viewBox="0 0 24 24" fill="{YELLOW}" stroke="{INK}" stroke-width="1.5"><path d="M12 2l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L12 17l-6.1 3.6 1.4-6.8L2.2 9.1l6.9-.8z"/></svg><div><b>{esc(title)}</b><br><span>{esc(why)}</span></div></div>'


def feed(items: list[tuple[str, str, str]]) -> str:
    """items: (headline, detail, colour)"""
    rows = "".join(f'<div class="it" style="--c:{c}">{esc(h)}<small>{esc(d)}</small></div>' for h, d, c in items)
    return f'<div class="feed">{rows}</div>'


def timeline(events) -> None:
    for e in events:
        note = f" &mdash; {esc(e['note'])}" if e["note"] else ""
        st.markdown(f'<div class="tl"><b>{esc(e["action"])}</b> by {esc(e["actor"])}{note}<br><span class="muted">{pretty_time(e["at"])}</span></div>', unsafe_allow_html=True)


def pretty_time(value: str) -> str:
    return value.replace("T", "  ")[:-3] if value else ""


def style_chart(chart):
    """Make an Altair chart match the design: warm background, no frame, orange marks."""
    return (chart.configure(background="transparent").configure_view(strokeWidth=0)
            .configure_axis(labelColor=GREY, titleColor=GREY, gridColor="#e4dccb", domainColor="#cfc5ad", labelFont="Barlow", titleFont="Barlow")
            .configure_legend(labelColor=GREY, titleColor=GREY).configure_title(color=INK, font="Barlow Condensed", fontSize=15))


def penalty_ticket(p, who: str = "") -> str:
    """A penalty or escalation shown like a challan: stub with the number and status, then the amount, the reason and who decided."""
    colour = {"Proposed": WARN, "Issued": BAD, "Disputed": WARN, "Paid": GOOD, "Waived": GREY, "Awaiting review": WARN, "Upheld": BAD, "Dismissed": GREY}.get(p["status"], GREY)
    is_penalty = p["kind"] == "penalty"
    headline = f'{p["currency"]} {p["amount"]:.0f}' if is_penalty else "Escalated to authority"
    decided = f'<div><b>Decided by</b>{esc(p["decided_by"])} on {esc(pretty_time(p["decided_at"]))}</div>' if p["decided_by"] else ""
    note = f'<div class="why"><b>Note:</b> {esc(p["note"])}</div>' if p["note"] else ""
    return (f'<div class="ticket"><div class="stub"><small>{"PENALTY" if is_penalty else "ESCALATION"}</small><div class="no">#{p["id"]:05d}</div>'
            f'<span class="chip" style="--c:{colour}">{esc(p["status"])}</span></div><div class="perf"></div>'
            f'<div class="body"><div class="what" style="color:{colour}">{esc(headline)}</div>'
            f'<div class="meta"><div><b>Raised</b>{esc(pretty_time(p["created_at"]))}</div><div><b>Violations</b>{p["violation_count"]}</div>{("<div><b>Who</b>" + esc(who) + "</div>") if who else ""}{decided}</div>'
            f'<div class="why">{esc(p["reason"])}</div>{note}</div></div>')
