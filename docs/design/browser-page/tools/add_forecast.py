"""Forecast to the end of the window, schedule-aware: a hatched 'ghost' from the current fill to the projected
value inside the usage bar, plus a second line under the reset time. Applies to Main and CardsView, then
regenerates MainBlocks (ghost cells hatched). Idempotent."""
import os, re
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

# projected % at reset (working hours Mon-Fri 09-19; sessions use raw time), computed from the sample data:
#   main  session 9% / 3h58m of 5h                   -> 11%
#   main  all 7d 22%, 36 working h elapsed, 14 left    -> 31%
#   main  Fable 74%, same clock                       -> 103%  runs out Tue ~12:30, 30 m before the Tue 13:00 reset
#   work  all 7d 61%, 19.5 wh elapsed, 30.5 left       -> 156%  runs out Tue ~15:00, 1d 18h before the Thu 09:30 reset
#   work  session: locked, no forecast;  ops: no data;  qa: stale (429), no forecast
FORECAST = {  # key: (label text fragment, reset text fragment) -> (projected %, note, is_warning)
    ("session 5h", "20:50"): (11, "→ 11% at reset", False),
    ("all 7d", "Tue 13:00"): (31, "→ 31% at reset", False),
    ("Fable 7d", "Tue 13:00"): (103, "runs out Tue ~12:30 · 30 m before reset", True),
    ("all 7d", "Thu 09:30"): (156, "runs out Tue ~15:00 · 1d 18h before reset", True),
}
ROW = re.compile(r'(<div style="display: grid; grid-template-columns: 100px [^"]*">)(.*?)(\n\s*</div>\n\s*</div>)', re.S)
BAR = re.compile(r'(<div style="position: relative; height: 10px; border-radius: 3px; background: (#[0-9a-f]{6});"><div style="position: absolute; left: 0; top: 0; bottom: 0; width: (\d+)%; background: (#[0-9a-f]{6}); border-radius: 3px;"></div>)(</div>)')
RESET = re.compile(r'(<div class="mono" style="font-size: 11px; color: (#[0-9a-f]{6}); text-align: right; white-space: nowrap;">)([^<]*)(</div>)')


def ghost(color, pct, proj):
    end = min(proj, 100)
    return (f'<div title="forecast {proj}% at reset · working hours Mon–Fri 09–19" style="position: absolute; left: {pct}%; width: {end - pct}%; top: 0; bottom: 0; '
            f'background: repeating-linear-gradient(135deg, {color} 0, {color} 2px, transparent 2px, transparent 5px); opacity: 0.75;"></div>')


def forecast_row(open_, body, close):
    if "forecast " in body:
        return open_ + body + close
    for (lab, rst), (proj, note, warn) in FORECAST.items():
        if lab in body and rst in body and "height: 10px" in body:
            m = BAR.search(body)
            if not m:
                break
            pct, color = int(m.group(3)), m.group(4)
            if proj <= pct:
                break
            body = BAR.sub(lambda mm: mm.group(1) + ghost(color, pct, proj) + mm.group(5), body, count=1)
            note_color = "#e0b04a" if warn else "#6d6786"
            body = RESET.sub(lambda mm: (f'<div style="display: flex; flex-direction: column; align-items: flex-end; gap: 1px; white-space: nowrap;">'
                                         f'<div class="mono" style="font-size: 11px; color: {mm.group(2)};">{mm.group(3)}</div>'
                                         f'<div class="mono" style="font-size: 10px; color: {note_color};">{note}</div></div>'), body, count=1)
            break
    return open_ + body + close


ROW_START = '<div style="display: grid; grid-template-columns: 100px'


def per_row(s):
    """Split on row starts so each limit row is handled on its own (a non-greedy regex merges rows in one block)."""
    parts = s.split(ROW_START)
    out = [parts[0]]
    n = 0
    for chunk in parts[1:]:
        # the row body ends where the account block closes or the next sibling begins; keep the tail untouched
        cut = chunk.find("\n      </div>")
        if cut < 0:
            cut = len(chunk)
        body, tail = chunk[:cut], chunk[cut:]
        out.append(forecast_row(ROW_START, body, "") + tail)
        n += 1
    return "".join(out), n


for f in ("Main.dc.html", "CardsView.dc.html"):
    s = open(f, encoding="utf-8").read()
    s, n = per_row(s)
    s = s.replace("thin line under a bar = share of the window already elapsed",
                  "thin line = share of the window elapsed · hatched = forecast at reset (working hours only)")
    open(f, "w", encoding="utf-8").write(s)
    print(f, "rows:", n, "forecasts:", s.count("forecast "))

# MainBlocks from Main: usage cells solid, forecast cells hatched, time bar unchanged
DARK = {'#3aa98c': '#33957b', '#e0b04a': '#c59b41', '#e0554f': '#c54b46', '#6d6786': '#605a76', '#2a2542': '#25203a', '#3d2438': '#362031'}
CELL, GAP = 8, 2
PITCH = CELL + GAP
N = 34
BAR_W = N * PITCH - GAP
FULL = re.compile(r'<div style="position: relative; height: 10px; border-radius: 3px; background: (#[0-9a-f]{6});"><div style="position: absolute; left: 0; top: 0; bottom: 0; width: (\d+)%; background: (#[0-9a-f]{6}); border-radius: 3px;"></div>(?:<div title="forecast (\d+)%[^"]*"[^>]*></div>)?</div>')


def grad(c):
    return f'repeating-linear-gradient(90deg, {c} 0, {c} {CELL}px, {DARK[c]} {CELL}px, {DARK[c]} {PITCH}px)'


def blocks(m):
    track, pct, color, proj = m.group(1), int(m.group(2)), m.group(3), m.group(4)
    filled = round(pct / 100 * N)
    fill_w = max(0, filled * PITCH - GAP) if filled < N else BAR_W
    out = (f'<div title="{pct}% · {filled} of {N} cells" style="position: relative; height: 10px; width: {BAR_W}px; max-width: 100%; border-radius: 3px; overflow: hidden; background: {grad(track)};">'
           f'<div style="position: absolute; left: 0; top: 0; bottom: 0; width: {fill_w}px; background: {grad(color)};"></div>')
    if proj:
        pcells = min(N, round(int(proj) / 100 * N))
        if pcells > filled:
            left = filled * PITCH
            width = (pcells - filled) * PITCH - GAP
            out += (f'<div title="forecast {proj}% at reset · working hours Mon–Fri 09–19" style="position: absolute; left: {left}px; width: {width}px; top: 0; bottom: 0; '
                    f'background: {grad(color)}; -webkit-mask: repeating-linear-gradient(135deg, #000 0, #000 2px, transparent 2px, transparent 5px); mask: repeating-linear-gradient(135deg, #000 0, #000 2px, transparent 2px, transparent 5px); opacity: 0.8;"></div>')
    return out + "</div>"


s = open("Main.dc.html", encoding="utf-8").read()
out, n = FULL.subn(blocks, s)
out = out.replace("grid-template-columns: 100px minmax(0, 1fr) 44px 170px;", f"grid-template-columns: 100px {BAR_W}px 44px 170px;")
out = out.replace("<!-- Header: title · live · updated · view toggle · refresh · settings -->",
                  "<!-- Header: title · live · updated · view toggle · refresh · settings — bar style: blocks (Settings → Bar style) -->")
open("MainBlocks.dc.html", "w", encoding="utf-8").write(out)
print("MainBlocks bars:", n)

# Settings: Forecast section before Polling
sp = open("SettingsPanel.dc.html", encoding="utf-8").read()
if "Forecast" not in sp:
    anchor = '''      <!-- Polling -->'''
    section = '''      <!-- Forecast -->
      <div style="display: flex; flex-direction: column; gap: 8px;">
        <div style="font-size: 11px; font-weight: 600; letter-spacing: 0.06em; text-transform: uppercase; color: #6d6786;">Forecast</div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
          <div>Show forecast at reset <span style="color: #9b95b5;">· hatched part of the bar</span></div>
          <div style="width: 36px; height: 20px; border-radius: 999px; background: #3aa98c; position: relative;"><div style="position: absolute; top: 2px; left: 18px; width: 16px; height: 16px; border-radius: 50%; background: #13111d;"></div></div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
          <div>Working days</div>
          <div style="display: flex; gap: 4px;">
            <span class="mono" style="width: 30px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 5px; background: #2a2542; color: #e8e8ee; font-size: 11px;">Mo</span>
            <span class="mono" style="width: 30px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 5px; background: #2a2542; color: #e8e8ee; font-size: 11px;">Tu</span>
            <span class="mono" style="width: 30px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 5px; background: #2a2542; color: #e8e8ee; font-size: 11px;">We</span>
            <span class="mono" style="width: 30px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 5px; background: #2a2542; color: #e8e8ee; font-size: 11px;">Th</span>
            <span class="mono" style="width: 30px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 5px; background: #2a2542; color: #e8e8ee; font-size: 11px;">Fr</span>
            <span class="mono" style="width: 30px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 5px; border: 1px solid #322c4a; color: #6d6786; font-size: 11px; box-sizing: border-box;">Sa</span>
            <span class="mono" style="width: 30px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 5px; border: 1px solid #322c4a; color: #6d6786; font-size: 11px; box-sizing: border-box;">Su</span>
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
          <div>Working hours</div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <div class="mono" style="width: 64px; height: 32px; display: flex; align-items: center; justify-content: center; border: 1px solid #3b3458; border-radius: 6px; background: #13111d; box-sizing: border-box;">09:00</div>
            <span style="color: #9b95b5;">–</span>
            <div class="mono" style="width: 64px; height: 32px; display: flex; align-items: center; justify-content: center; border: 1px solid #3b3458; border-radius: 6px; background: #13111d; box-sizing: border-box;">19:00</div>
          </div>
        </div>
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
          <div>Usage outside working hours</div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div class="mono" style="width: 64px; height: 32px; display: flex; align-items: center; justify-content: flex-end; padding: 0 10px; border: 1px solid #3b3458; border-radius: 6px; background: #13111d; box-sizing: border-box;">0%</div>
            <span style="color: #9b95b5; font-size: 12px;">of the working rate</span>
          </div>
        </div>
        <div style="font-size: 12px; color: #6d6786;">Rate = usage over the last working hours from the 5-min history; the 5 h session window uses plain clock time.</div>
      </div>

'''
    assert anchor in sp
    sp = sp.replace(anchor, section + anchor, 1).replace("min-height: 1230px", "min-height: 1500px")
    open("SettingsPanel.dc.html", "w", encoding="utf-8").write(sp)
    print("settings forecast section added")

# Stats tile: make the pace tile schedule-aware
st = open("StatsView.dc.html", encoding="utf-8").read()
st2 = st.replace("main@example.com · Fable reaches 100% about Thu 21:00", "main@example.com · Fable runs out Tue ~12:30, 30 m before reset · working hours only")
st2 = st2.replace(">+9%/day<", ">+2.1%/h<").replace(">Weekly pace<", ">Pace · working hours<")
if st2 != st:
    open("StatsView.dc.html", "w", encoding="utf-8").write(st2)
    print("stats tile updated")
