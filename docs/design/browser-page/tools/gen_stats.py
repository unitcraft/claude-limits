"""StatsView (per account, three limit windows) and StatsFolders (per credential folder, 30 days).
Written with the first-round tokens; retheme.py maps them to the Nova site tokens afterwards."""
import os, math
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

W, H = 280, 84
TOP, BOT = 8, 68
TEAL, VIOLET, ORANGE, GREY = "#3aa98c", "#a27bd0", "#cf6f4a", "#6b6e76"   # validated on the Nova surface
RED, AMBER = "#e0554f", "#e0b04a"
MONO = "IBM Plex Mono, ui-monospace, monospace"


def y(p): return BOT - (BOT - TOP) * p / 100.0
def x(t, span, w=W): return w * t / span
def path(pts): return "M " + " L ".join(f"{px:.1f},{py:.1f}" for px, py in pts)
def area(pts): return path(pts) + f" L {pts[-1][0]:.1f},{BOT} L {pts[0][0]:.1f},{BOT} Z"


def sawtooth(span, segs, w=W):
    pts = []
    for (a, b, pa, pb) in segs:
        pts.append((x(a, span, w), y(pa))); pts.append((x(b, span, w), y(pb)))
    return pts


def grid(w=W):
    return "".join(f'<line x1="0" x2="{w}" y1="{y(p):.1f}" y2="{y(p):.1f}" stroke="#2a2b31" stroke-width="1"></line>' for p in (0, 50, 100))


def ticks(labels, span, w=W):
    return "".join(f'<text x="{x(t, span, w):.1f}" y="{H - 2}" fill="#6b6e76" font-size="10" font-family="{MONO}" text-anchor="{anc}">{lab}</text>' for t, lab, anc in labels)


def resets(ts, span, w=W):
    return "".join(f'<line x1="{x(t, span, w):.1f}" x2="{x(t, span, w):.1f}" y1="{TOP}" y2="{BOT}" stroke="#4a4c54" stroke-dasharray="2 3"></line>' for t in ts)


def band(t0, t1, span, color, op=0.18, w=W):
    return f'<rect x="{x(t0, span, w):.1f}" y="{TOP}" width="{x(t1, span, w) - x(t0, span, w):.1f}" height="{BOT - TOP}" fill="{color}" fill-opacity="{op}"></rect>'


def svg(inner, w=W, h=H):
    return f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display: block; overflow: visible; max-width: 100%;" aria-hidden="true">{inner}</svg>'


def line(pts, color, dashed=False, fill=True):
    d = ' stroke-dasharray="5 4"' if dashed else ''
    out = f'<path d="{area(pts)}" fill="{color}" fill-opacity="0.12"></path>' if fill else ''
    return out + f'<path d="{path(pts)}" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"{d}></path>'


def chart(series, span, tick_labels, reset_ts=(), extra_under="", extra_over="", w=W):
    """series: list of (pts, color, dashed, fill)"""
    inner = grid(w) + extra_under + resets(reset_ts, span, w)
    for pts, color, dashed, fill in series:
        inner += line(pts, color, dashed, fill)
    return svg(inner + extra_over + ticks(tick_labels, span, w), w)


day_ticks = [(0, "20:00", "start"), (6, "02:00", "middle"), (12, "08:00", "middle"), (18, "14:00", "middle"), (24, "now", "end")]
week_ticks = [(0, "Sat", "start"), (2, "Mon", "middle"), (4, "Wed", "middle"), (6, "Fri", "middle"), (7, "now", "end")]
month_ticks = [(0, "Aug 7", "start"), (7.5, "Aug 15", "middle"), (15, "Aug 22", "middle"), (22.5, "Aug 30", "middle"), (30, "now", "end")]

# ───────────────────────── shared chrome ─────────────────────────
HEAD = """<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
  <style>
    body { margin: 0; background: #16171a; color: #ecebe6; font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif; font-size: 13px; line-height: 1.35; -webkit-font-smoothing: antialiased; }
    a { color: #7fc7ad; } a:hover { color: #a3dcc6; }
    .mono { font-family: "IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace; }
    @keyframes live-pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.35; } }
    .live-dot { animation: live-pulse 2.4s ease-in-out infinite; }
    .icon-btn:hover { background: #2a2b31; color: #ecebe6; }
  </style>
</helmet>
"""
ICON_LIST = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="4" y1="7" x2="20" y2="7"></line><line x1="4" y1="12" x2="20" y2="12"></line><line x1="4" y1="17" x2="20" y2="17"></line></svg>'
ICON_CARDS = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><rect x="3" y="4" width="18" height="6" rx="1.5"></rect><rect x="3" y="14" width="18" height="6" rx="1.5"></rect></svg>'
ICON_STATS = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 17 9 11 13 15 21 7"></polyline><polyline points="15 7 21 7 21 13"></polyline></svg>'
ICON_REFRESH = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 12a8 8 0 1 1-2.34-5.66"></path><polyline points="20 4 20 9 15 9"></polyline></svg>'
ICON_GEAR = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"></path></svg>'
LOCK = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#f0716b" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="11" width="16" height="10" rx="2"></rect><path d="M8 11V7a4 4 0 0 1 8 0v4"></path></svg>'
FOLDER = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#9a9ca3" stroke-width="2" stroke-linejoin="round" aria-hidden="true"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path></svg>'


def tab(title, svg_icon, active):
    st = "background: #2a2b31; color: #ecebe6; cursor: default;" if active else "color: #9a9ca3; cursor: pointer;"
    return f'<div role="tab" title="{title}" style="display: flex; align-items: center; justify-content: center; width: 38px; height: 32px; border-radius: 6px; {st}">{svg_icon}</div>'


def btn(title, icon):
    return f'<button class="icon-btn" type="button" title="{title}" style="width: 44px; height: 44px; display: flex; align-items: center; justify-content: center; border: 1px solid #2c2d33; border-radius: 8px; background: #1f2025; color: #9a9ca3; cursor: pointer;">{icon}</button>'


def header():
    return f"""
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 2px;">
      <div style="display: flex; align-items: center; gap: 10px;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ecebe6" stroke-width="2" stroke-linecap="round" aria-hidden="true"><line x1="4" y1="7" x2="20" y2="7"></line><line x1="4" y1="12" x2="14" y2="12"></line><line x1="4" y1="17" x2="17" y2="17"></line></svg>
        <div style="font-size: 15px; font-weight: 600;">claude-limits</div>
        <span class="live-dot" title="live" style="display: inline-block; width: 7px; height: 7px; border-radius: 50%; background: #3aa98c; margin-left: 6px;"></span>
        <div class="mono" style="color: #9a9ca3; font-size: 12px;">19:47 · 15 s ago</div>
      </div>
      <div style="display: flex; align-items: center; gap: 8px;">
        <div role="tablist" style="display: flex; padding: 3px; border: 1px solid #2c2d33; border-radius: 9px; background: #1a1b1f;">
          {tab("List", ICON_LIST, False)}
          {tab("Cards", ICON_CARDS, False)}
          {tab("Stats", ICON_STATS, True)}
        </div>
        {btn("Refresh now", ICON_REFRESH)}
        {btn("Settings", ICON_GEAR)}
      </div>
    </div>
"""


def seg(items, active):
    out = '<div role="tablist" style="display: flex; padding: 3px; border: 1px solid #2c2d33; border-radius: 8px; background: #1a1b1f;">'
    for it in items:
        st = "background: #2a2b31; color: #ecebe6; font-weight: 500;" if it == active else "color: #9a9ca3;"
        out += f'<div role="tab" style="height: 28px; padding: 0 12px; display: flex; align-items: center; border-radius: 5px; font-size: 12px; {st}">{it}</div>'
    return out + "</div>"


def tile(label, value, sub, color="#ecebe6"):
    return f"""<div style="flex: 1; display: flex; flex-direction: column; gap: 4px; padding: 12px 14px; background: #1f2025; border: 1px solid #2c2d33; border-radius: 12px;">
        <div style="font-size: 11px; color: #9a9ca3;">{label}</div>
        <div class="mono" style="font-size: 20px; font-weight: 600; color: {color}; line-height: 1.1;">{value}</div>
        <div style="font-size: 11px; color: #6b6e76;">{sub}</div>
      </div>"""


def swatch(color, label, dashed=False):
    mark = (f'<span style="display: inline-block; width: 14px; height: 0; border-top: 2px dashed {color};"></span>' if dashed
            else f'<span style="display: inline-block; width: 10px; height: 10px; border-radius: 3px; background: {color};"></span>')
    return f'<span style="display: inline-flex; align-items: center; gap: 6px; color: #9a9ca3; font-size: 11px;">{mark}{label}</span>'


def col(caption_left, caption_right, chart_svg, mut="#9a9ca3", op=""):
    return f"""<div style="display: flex; flex-direction: column; gap: 6px; min-width: 0;{op}">
          <div style="display: flex; justify-content: space-between; gap: 8px; font-size: 11px; color: {mut}; white-space: nowrap;"><span>{caption_left}</span><span class="mono">{caption_right}</span></div>
          {chart_svg}
        </div>"""


def card(ident, cols, tint=False, strip=""):
    bg, bd = ("#2a1d1f", "#4d2c30") if tint else ("#1f2025", "#2c2d33")
    strip_html = f'<div style="grid-column: 2 / span 3;">{strip}</div>' if strip else ""
    return f"""
      <section style="display: grid; grid-template-columns: 190px repeat(3, minmax(0, 1fr)); gap: 12px 16px; align-items: start; padding: 14px 16px 12px; background: {bg}; border: 1px solid {bd}; border-radius: 12px;">
        <div style="display: flex; flex-direction: column; gap: 6px; line-height: 1.4; grid-row: span 2;">{ident}</div>
        {strip_html}
        {"".join(cols)}
      </section>"""


def page(body_inner, min_h):
    return HEAD + f"""
<div style="min-height: {min_h}px; background: #16171a; display: flex; flex-direction: column; align-items: center; padding: 24px 24px 32px; box-sizing: border-box;">
  <div style="width: 100%; max-width: 1120px; display: flex; flex-direction: column; gap: 12px;">
{header()}
{body_inner}
  </div>
</div>
</x-dc>
</body>
</html>
"""


# ───────────────────────── StatsView: per account, three windows ─────────────────────────
main_s = sawtooth(24, [(0, 2, 12, 48), (2, 5, 48, 55), (5, 5.01, 55, 0), (5.01, 13.5, 0, 3), (13.5, 13.51, 3, 0), (13.51, 16, 0, 41), (16, 18.5, 41, 62), (18.5, 18.51, 62, 0), (18.51, 21, 0, 9), (21, 24, 9, 9)])
hx, hy = x(17.2, 24), y(57)
hover = (f'<line x1="{hx:.1f}" x2="{hx:.1f}" y1="{TOP}" y2="{BOT}" stroke="#9a9ca3" stroke-width="1"></line>'
         f'<circle cx="{hx:.1f}" cy="{hy:.1f}" r="4" fill="{TEAL}" stroke="#1f2025" stroke-width="2"></circle>'
         f'<rect x="{hx - 92:.1f}" y="{TOP - 6}" width="86" height="22" rx="5" fill="#2a2b31" stroke="#3a3b42"></rect>'
         f'<text x="{hx - 49:.1f}" y="{TOP + 9}" fill="#ecebe6" font-size="10.5" font-family="{MONO}" text-anchor="middle">13:12 · 57%</text>')
main_w = sawtooth(7, [(0, 1, 4, 7), (1, 2, 7, 9), (2, 3, 9, 14), (3, 4, 14, 19), (4, 5, 19, 21), (5, 6, 21, 22), (6, 7, 22, 22)])
main_fable = sawtooth(7, [(0, 1, 10, 22), (1, 2, 22, 30), (2, 3, 30, 44), (3, 4, 44, 58), (4, 5, 58, 66), (5, 6, 66, 72), (6, 7, 72, 74)])
main_opus = sawtooth(7, [(0, 2, 2, 4), (2, 4, 4, 9), (4, 6, 9, 11), (6, 7, 11, 12)])

work_s = sawtooth(24, [(0, 3, 30, 70), (3, 4.5, 70, 71), (4.5, 4.51, 71, 0), (4.51, 13, 0, 6), (13, 18.3, 6, 100), (18.3, 20, 100, 100), (20, 20.01, 100, 0), (20.01, 23, 0, 100), (23, 24, 100, 100)])
work_lock = band(18.3, 20, 24, RED) + band(23, 24, 24, RED)
work_w = sawtooth(7, [(0, 2, 40, 49), (2, 3, 49, 52), (3, 3.01, 52, 0), (3.01, 4, 0, 18), (4, 5, 18, 38), (5, 6, 38, 55), (6, 7, 55, 61)])

qa_s = sawtooth(24, [(0, 6, 20, 26), (6, 6.01, 26, 0), (6.01, 15, 0, 12), (15, 20, 12, 35), (20, 23.7, 35, 41)])
qa_w = sawtooth(7, [(0, 3, 30, 44), (3, 5, 44, 50), (5, 6.96, 50, 58)])
qa_opus = sawtooth(7, [(0, 3, 2, 6), (3, 5, 6, 9), (5, 6.96, 9, 12)])
qa_gap = band(23.7, 24, 24, AMBER, 0.15)
flat = f'<line x1="0" x2="{W}" y1="{y(0):.1f}" y2="{y(0):.1f}" stroke="#4a4c54" stroke-width="2" stroke-dasharray="4 4"></line>'

legend_models = f'<div style="display: flex; gap: 14px;">{swatch(TEAL, "Fable")}{swatch(ORANGE, "Opus")}</div>'

acc_main = card(
    '<div style="font-weight: 600;">main@example.com</div><div style="font-size: 12px; color: #9a9ca3;">Tech Center</div><div class="mono" style="font-size: 11px; color: #6b6e76;">nv-lang</div><div style="margin-top: 6px; font-size: 11px; color: #9a9ca3;">peak 62% · never locked</div>',
    [col("session · 24 h", "now 9%", chart([(main_s, TEAL, False, True)], 24, day_ticks, [5, 13.5, 18.5], "", hover)),
     col("all models · 7 d", "now 22%", chart([(main_w, TEAL, False, True)], 7, week_ticks)),
     col("per model · 7 d", "Fable 74% · Opus 12%", chart([(main_fable, TEAL, False, False), (main_opus, ORANGE, False, False)], 7, week_ticks))])
acc_work = card(
    '<div style="display: flex; align-items: center; gap: 6px; font-weight: 600;">work@example.org ' + LOCK + '</div><div style="font-size: 12px; color: #a89a9b;">Personal</div><div class="mono" style="font-size: 11px; color: #a89a9b;">dev · dev-wsl</div><div style="margin-top: 6px; font-size: 11px; color: #f0716b;">locked 2h 10m this week</div>',
    [col("session · 24 h", '<span style="color: #f0716b;">now 100%</span>', chart([(work_s, TEAL, False, True)], 24, day_ticks, [4.5, 20], work_lock), "#a89a9b"),
     col("all models · 7 d", "now 61%", chart([(work_w, TEAL, False, True)], 7, week_ticks, [3]), "#a89a9b"),
     col("per model · 7 d", "no per-model limit on this plan", svg(grid() + flat + ticks(week_ticks, 7)), "#a89a9b")], tint=True)
acc_ops = card(
    '<div style="font-weight: 600; color: #9a9ca3;">ops@example.org</div><div style="font-size: 12px; color: #6b6e76;">Example Inc</div><div class="mono" style="font-size: 11px; color: #6b6e76;">ops</div><div style="margin-top: 6px; font-size: 11px; color: #9a9ca3;">no data since 5 Sep 18:02 · token expired</div>',
    [col("session · 24 h", "no data", svg(grid() + flat + ticks(day_ticks, 24)), op=" opacity: 0.6;"),
     col("all models · 7 d", "no data", svg(grid() + flat + ticks(week_ticks, 7)), op=" opacity: 0.6;"),
     col("per model · 7 d", "no data", svg(grid() + flat + ticks(week_ticks, 7)), op=" opacity: 0.6;")])
acc_qa = card(
    '<div style="font-weight: 600;">qa@example.org</div><div style="font-size: 12px; color: #9a9ca3;">Example Inc</div><div class="mono" style="font-size: 11px; color: #6b6e76;">qa</div><div style="margin-top: 6px; font-size: 11px; color: #e0b04a;">gap since 19:41 · HTTP 429</div>',
    [col("session · 24 h", "41% at 19:41", chart([(qa_s, TEAL, False, True)], 24, day_ticks, [6], qa_gap)),
     col("all models · 7 d", "58% at 19:41", chart([(qa_w, TEAL, False, True)], 7, week_ticks)),
     col("per model · 7 d", "Opus 12%", chart([(qa_opus, ORANGE, False, False)], 7, week_ticks))])

stats_body = f"""
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 2px; flex-wrap: wrap;">
      <div style="display: flex; align-items: center; gap: 10px;">
        {seg(["24 h", "7 d", "30 d"], "7 d")}
        {seg(["Accounts", "Folders"], "Accounts")}
      </div>
      <div style="display: flex; align-items: center; gap: 14px;">{legend_models}<span style="font-size: 11px; color: #6b6e76;">per-model column</span></div>
    </div>

    <div style="display: flex; gap: 10px;">
      {tile("Locked this week", "2h 10m", "work@example.org · Tue 14:20–16:00, Fri 19:00–now", "#f0716b")}
      {tile("Peak session", "100%", "work@example.org · twice")}
      {tile("Avg session window", "38%", "across 3 live logins")}
      {tile("Weekly pace", "+9%/day", "main@example.com · Fable reaches 100% about Thu 21:00", "#e0b04a")}
    </div>

    <div style="display: flex; flex-direction: column; gap: 10px;">
{acc_main}
{acc_work}
{acc_ops}
{acc_qa}
    </div>

    <div style="display: flex; justify-content: space-between; gap: 12px; font-size: 11px; color: #6b6e76; padding: 0 2px;">
      <div>three columns = the three limit windows · dashed verticals = resets · red band = locked · amber band = no data</div>
      <div class="mono">samples every 5 min · kept 30 days</div>
    </div>
"""
open("StatsView.dc.html", "w", encoding="utf-8").write(page(stats_body, 960))
print("StatsView written")

# ───────────────────────── StatsFolders: per credential folder, 30 days ─────────────────────────
SPAN = 30
ACC = {"main": (TEAL, "main@example.com"), "work": (VIOLET, "work@example.org"), "qa": (ORANGE, "qa@example.org"), "none": (GREY, "no login")}


def occupancy_bands(segs, w=W, op=0.10):
    return "".join(band(a, b, SPAN, ACC[k][0], op, w) for a, b, k in segs if k != "none")


def daily_peaks(a, b, k, seed):
    """One point per day inside [a,b): a deterministic wobble per account so the line reads as real data."""
    base, amp = {"main": (42, 18), "work": (78, 22), "qa": (28, 12)}[k]
    pts = []
    d = a
    i = 0
    while d < b - 1e-9:
        v = base + amp * math.sin(seed + i * 1.7) * 0.6 + amp * 0.4 * math.sin(seed * 2 + i * 0.6)
        v = max(4, min(100, v))
        pts.append((x(d + 0.5, SPAN), y(v)))
        d += 1; i += 1
    return pts


def weekly_saw(a, b, k, reset_day, start_pct, rate):
    """All-models 7d window: climbs at `rate` %/day, drops to ~0 on the account's reset weekday."""
    pts = []
    d = a
    v = start_pct
    while d < b - 1e-9:
        nxt = min(b, d + 0.5)
        pts.append((x(d, SPAN), y(v)))
        v = min(100, v + rate * (nxt - d))
        d = nxt
        if abs((d - reset_day) % 7) < 1e-9 and d < b:
            pts.append((x(d, SPAN), y(v)))
            v = 2
    pts.append((x(min(b, d), SPAN), y(v)))
    return pts


def folder_charts(segs):
    """segs: list of (day0, day1, account). Returns three chart svgs whose lines are colored by account and break at switches."""
    s_series, w_series, m_series = [], [], []
    seed = 1.0
    for a, b, k in segs:
        if k == "none":
            continue
        c = ACC[k][0]
        s_series.append((daily_peaks(a, b, k, seed), c, False, False))
        reset_day, rate = {"main": (2, 3.2), "work": (4, 9.0), "qa": (6, 6.5)}[k]
        w_series.append((weekly_saw(a, b, k, reset_day, 6, rate), c, False, True))
        m_series.append((weekly_saw(a, b, k, reset_day, 10, rate * 1.15), c, False, False))
        if k != "work":   # Opus as the second model, dashed
            m_series.append((weekly_saw(a, b, k, reset_day, 2, rate * 0.25), c, True, False))
        seed += 2.3
    under = occupancy_bands(segs)
    lock = band(15.2, 15.8, SPAN, RED) + band(18.6, 19.2, SPAN, RED) if any(k == "work" for _, _, k in segs) else ""
    none_band = "".join(band(a, b, SPAN, GREY, 0.18) for a, b, k in segs if k == "none")
    switches = [a for a, _, _ in segs[1:]]
    return (chart(s_series, SPAN, month_ticks, switches, under + none_band + lock),
            chart(w_series, SPAN, month_ticks, switches, under + none_band),
            chart(m_series, SPAN, month_ticks, switches, under + none_band))


def strip(segs, w=W * 3 + 32):
    """Who was logged into this folder when: labelled segments over 30 days."""
    inner = ""
    for a, b, k in segs:
        c, label = ACC[k][0], ACC[k][1]
        short = label.split("@")[0] + "@" if k != "none" else "no login"
        x0, x1 = x(a, SPAN, w), x(b, SPAN, w)
        inner += f'<rect x="{x0:.1f}" y="2" width="{x1 - x0 - 2:.1f}" height="18" rx="4" fill="{c}" fill-opacity="{0.35 if k != "none" else 0.25}"></rect>'
        if x1 - x0 > 46:
            inner += f'<text x="{x0 + 8:.1f}" y="15" fill="#ecebe6" font-size="11" font-family="{MONO}">{short}</text>'
    return f'<svg width="{w}" height="22" viewBox="0 0 {w} 22" style="display: block; max-width: 100%;" aria-hidden="true">{inner}</svg>'


def folder_card(path_label, sub, segs, now_line, tint=False):
    s_svg, w_svg, m_svg = folder_charts(segs)
    mut = "#a89a9b" if tint else "#9a9ca3"
    ident = (f'<div style="display: flex; align-items: center; gap: 6px; font-weight: 600;">{FOLDER}{path_label}</div>'
             f'<div style="font-size: 12px; color: {mut};">{sub}</div>'
             f'<div style="margin-top: 6px; font-size: 11px; color: {mut};">{now_line}</div>')
    return card(ident,
                [col("session · daily peak", "", s_svg, mut), col("all models · 7 d window", "", w_svg, mut), col("per model · 7 d window", "solid Fable · dashed Opus", m_svg, mut)],
                tint=tint, strip=strip(segs))


dev_segs = [(0, 9, "main"), (9, 22, "work"), (22, 27, "main"), (27, 30, "qa")]
nv_segs = [(0, 30, "main")]
ops_segs = [(0, 26, "qa"), (26, 30, "none")]

legend_accounts = f'<div style="display: flex; gap: 14px; flex-wrap: wrap;">{swatch(TEAL, "main@example.com")}{swatch(VIOLET, "work@example.org")}{swatch(ORANGE, "qa@example.org")}{swatch(GREY, "no login")}{swatch("#9a9ca3", "Opus", dashed=True)}</div>'

folders_body = f"""
    <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0 2px; flex-wrap: wrap;">
      <div style="display: flex; align-items: center; gap: 10px;">
        {seg(["24 h", "7 d", "30 d"], "30 d")}
        {seg(["Accounts", "Folders"], "Folders")}
      </div>
      {legend_accounts}
    </div>

    <div style="display: flex; gap: 10px;">
      {tile("Login switches · 30 d", "4", "dev: main → work → main → qa")}
      {tile("Locked while in a folder", "6h 40m", "all of it under work@example.org in dev", "#f0716b")}
      {tile("Folder with most logins", "dev", "3 accounts in 30 days")}
      {tile("Days without a login", "4", "ops · token expired 5 Sep", "#e0b04a")}
    </div>

    <div style="display: flex; flex-direction: column; gap: 10px;">
{folder_card("dev", "C:/accounts/dev", dev_segs, "now: qa@example.org · since Sep 3", tint=False)}
{folder_card("nv-lang", "C:/accounts/nv-lang", nv_segs, "now: main@example.com · whole month")}
{folder_card("ops", "C:/accounts/ops", ops_segs, "no login since Sep 2 · token expired")}
    </div>

    <div style="display: flex; justify-content: space-between; gap: 12px; font-size: 11px; color: #6b6e76; padding: 0 2px;">
      <div>a folder is a person's seat: the strip shows which account was logged in when; lines take the account's colour and break at a switch · red band = locked</div>
      <div class="mono">30 d · samples every 5 min</div>
    </div>
"""
open("StatsFolders.dc.html", "w", encoding="utf-8").write(page(folders_body, 900))
print("StatsFolders written")
