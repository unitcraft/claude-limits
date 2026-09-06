"""Add a thin 'time elapsed' bar under every usage bar in Main and CardsView, then regenerate MainBlocks.
The time bar shows how much of the limit window (5 h or 7 d) has already passed, so usage can be read against pace."""
import os, re
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

TIME_FILL = "#7a6fa0"          # muted violet: not a status colour, not the series teal
ROW = re.compile(r'(<div style="display: grid; grid-template-columns: 100px [^"]*">)(.*?)(\n\s*</div>)', re.S)
BAR = re.compile(r'<div style="position: relative; height: 10px; border-radius: 3px; background: (#[0-9a-f]{6});"><div style="position: absolute; left: 0; top: 0; bottom: 0; width: (\d+)%; background: (#[0-9a-f]{6}); border-radius: 3px;"></div></div>')
LEFT = re.compile(r'\((?:(\d+)d )?(?:(\d+)h)?(?: ?(\d+)m)?\)')


def minutes_left(row):
    m = LEFT.search(row)
    if not m:
        return None
    d, h, mi = (int(v) if v else 0 for v in m.groups())
    return d * 1440 + h * 60 + mi


def fmt(mins):
    d, r = divmod(mins, 1440)
    h, mi = divmod(r, 60)
    if d:
        return f"{d}d {h:02d}h"
    return f"{h}h {mi:02d}m"


def add_time(row_open, row_body, row_close):
    if "height: 10px" not in row_body:
        return row_open + row_body + row_close
    window = 300 if "session" in row_body else 7 * 1440
    left = minutes_left(row_body)
    if left is None:
        return row_open + row_body + row_close
    elapsed = max(0, window - left)
    pct = round(elapsed / window * 100)

    def wrap(m):
        track = m.group(1)
        return (f'<div style="display: flex; flex-direction: column; gap: 3px;">{m.group(0)}'
                f'<div title="time elapsed {pct}% · {fmt(elapsed)} of {fmt(window)}" style="position: relative; height: 3px; border-radius: 2px; background: {track};">'
                f'<div style="position: absolute; left: 0; top: 0; bottom: 0; width: {pct}%; background: {TIME_FILL}; border-radius: 2px;"></div></div></div>')
    return row_open + BAR.sub(wrap, row_body, count=1) + row_close


for f in ("Main.dc.html", "CardsView.dc.html"):
    s = open(f, encoding="utf-8").read()
    if "time elapsed" in s:
        print(f, "already has time bars"); continue
    s, n = ROW.subn(lambda m: add_time(m.group(1), m.group(2), m.group(3)), s)
    s = s.replace("<div>127.0.0.1:7391 · 4 logins in 5 directories</div>",
                  "<div>127.0.0.1:7391 · 4 logins in 5 directories · thin line under a bar = share of the window already elapsed</div>")
    open(f, "w", encoding="utf-8").write(s)
    print(f, "rows:", n, "time bars:", s.count("time elapsed"))

# MainBlocks: regenerate from Main (block bars for usage, the time bar stays a thin solid line)
DARK = {'#3aa98c': '#33957b', '#e0b04a': '#c59b41', '#e0554f': '#c54b46', '#6d6786': '#605a76', '#2a2542': '#25203a', '#3d2438': '#362031'}
CELL, GAP = 8, 2
PITCH = CELL + GAP
N = 34
BAR_W = N * PITCH - GAP


def grad(c):
    return f'repeating-linear-gradient(90deg, {c} 0, {c} {CELL}px, {DARK[c]} {CELL}px, {DARK[c]} {PITCH}px)'


def blocks(m):
    track, pct, color = m.group(1), int(m.group(2)), m.group(3)
    filled = round(pct / 100 * N)
    fill_w = max(0, filled * PITCH - GAP) if filled < N else BAR_W
    return (f'<div title="{pct}% · {filled} of {N} cells" style="position: relative; height: 10px; width: {BAR_W}px; max-width: 100%; border-radius: 3px; overflow: hidden; background: {grad(track)};">'
            f'<div style="position: absolute; left: 0; top: 0; bottom: 0; width: {fill_w}px; background: {grad(color)};"></div></div>')


s = open("Main.dc.html", encoding="utf-8").read()
out, n = BAR.subn(blocks, s)
out = out.replace("grid-template-columns: 100px minmax(0, 1fr) 44px 170px;", f"grid-template-columns: 100px {BAR_W}px 44px 170px;")
out = out.replace("<!-- Header: title · live · updated · view toggle · refresh · settings -->",
                  "<!-- Header: title · live · updated · view toggle · refresh · settings — bar style: blocks (Settings → Bar style) -->")
open("MainBlocks.dc.html", "w", encoding="utf-8").write(out)
print("MainBlocks bars:", n)

# Settings: toggle under "Reset time"
sp = open("SettingsPanel.dc.html", encoding="utf-8").read()
if "Time elapsed bar" not in sp:
    anchor = '''        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
          <div>Hide logins with an expired token</div>'''
    row = '''        <div style="display: flex; align-items: center; justify-content: space-between; gap: 12px;">
          <div>Time elapsed bar <span style="color: #9b95b5;">· thin line under each bar</span></div>
          <div style="width: 36px; height: 20px; border-radius: 999px; background: #3aa98c; position: relative;"><div style="position: absolute; top: 2px; left: 18px; width: 16px; height: 16px; border-radius: 50%; background: #13111d;"></div></div>
        </div>
'''
    assert anchor in sp
    sp = sp.replace(anchor, row + anchor, 1).replace("min-height: 1180px", "min-height: 1230px")
    open("SettingsPanel.dc.html", "w", encoding="utf-8").write(sp)
    print("settings toggle added")
