"""Re-tint the dark artboards with the Nova site tokens (www/site/src/styles/global.css, dark scheme)."""
import os, re
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

MAP = [
    # fonts
    ('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap',
     'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap'),
    ('"IBM Plex Sans", "Segoe UI", system-ui, sans-serif', '"Manrope", "Segoe UI", system-ui, sans-serif'),
    ('"IBM Plex Mono", ui-monospace, "Cascadia Mono", Consolas, monospace', '"JetBrains Mono", ui-monospace, "Cascadia Mono", Consolas, monospace'),
    ('IBM Plex Mono, ui-monospace, monospace', 'JetBrains Mono, ui-monospace, monospace'),
    # surfaces (site: --bg #0f0f14, --bg-alt #191921, --surface #1b1b26, --border #2a2a38, --border-soft #222230)
    ('#16171a', '#0f0f14'),
    ('#1f2025', '#1b1b26'),
    ('#1a1b1f', '#191921'),
    ('#2c2d33', '#2a2a38'),
    ('#34353c', '#33334a'),
    ('#3a3b42', '#3c3c55'),
    ('#2a2b31', '#25253a'),
    ('#4a4c54', '#4a4a62'),
    # ink (site: --fg #e8e8ee, --fg-muted #9494aa, --fg-subtle #66667a)
    ('#ecebe6', '#e8e8ee'),
    ('#c9c8c2', '#c9c9d6'),
    ('#9a9ca3', '#9494aa'),
    ('#6b6e76', '#66667a'),
    # links -> Nova accent
    ('a { color: #7fc7ad; } a:hover { color: #a3dcc6; }', 'a { color: #a97dd1; } a:hover { color: #bf99e0; }'),
    # series / status: validated teal on the Nova surface
    ('#45c0a0', '#3aa98c'),
    # red tint on the violet-black base
    ('#2a1d1f', '#2b1c27'),
    ('#4d2c30', '#4f2b3b'),
    ('#3a2527', '#3a2534'),
    ('#5a3236', '#5a3247'),
    ('#6a3a3f', '#6a3a4f'),
    ('#a89a9b', '#a898ac'),
    ('#d9c9ca', '#d8c9d8'),
]

# active tab / selected segment gets the accent-light treatment (site: --accent-light #2a1e3a, --accent #a97dd1)
ACTIVE_TAB_OLD = 'background: #25253a; color: #e8e8ee; cursor: default;'
ACTIVE_TAB_NEW = 'background: #2a1e3a; color: #cdb3ea; cursor: default;'
ACTIVE_SEG_OLD = 'background: #25253a; color: #e8e8ee; font-weight: 500;'
ACTIVE_SEG_NEW = 'background: #2a1e3a; color: #cdb3ea; font-weight: 500;'

files = [f for f in os.listdir('.') if f.endswith('.dc.html') and f not in ('DenseTable.dc.html', 'CardsGrid.dc.html')]
for f in files:
    s = open(f, encoding='utf-8').read()
    o = s
    for a, b in MAP:
        s = s.replace(a, b)
    s = s.replace(ACTIVE_TAB_OLD, ACTIVE_TAB_NEW).replace(ACTIVE_SEG_OLD, ACTIVE_SEG_NEW)
    open(f, 'w', encoding='utf-8').write(s)
    print(f, 'changed' if s != o else 'unchanged')
