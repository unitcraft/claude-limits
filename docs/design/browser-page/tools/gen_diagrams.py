"""DbSchema.dc.html (ER diagram of plan 01.2 §3) and ApiMap.dc.html (route map of plan 01.3) in the Nova dark theme.
Boxes are absolutely positioned HTML, connectors are one SVG overlay with coordinates computed here."""
import os
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

BG = "radial-gradient(1100px 520px at 18% -8%, rgba(107, 63, 160, 0.30), transparent 62%), radial-gradient(900px 500px at 92% 110%, rgba(107, 63, 160, 0.16), transparent 60%), #13111d"
SURF, ALT, BORDER, BORDER2, TRACK = "#1e1a2e", "#181526", "#322c4a", "#3b3458", "#2a2542"
FG, SOFT, MUTED, SUBTLE = "#e8e8ee", "#cbc7da", "#9b95b5", "#6d6786"
TEAL, VIOLET, ORANGE, AMBER, RED = "#3aa98c", "#a27bd0", "#cf6f4a", "#e0b04a", "#e0554f"
MONO = '"JetBrains Mono", ui-monospace, Consolas, monospace'

HEAD = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script src="./support.js"></script>
</head>
<body>
<x-dc>
<helmet>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap">
  <style>
    body {{ margin: 0; background: {BG}; color: {FG}; font-family: "Manrope", "Segoe UI", system-ui, sans-serif; font-size: 12px; line-height: 1.35; -webkit-font-smoothing: antialiased; }}
    a {{ color: #7fc7ad; }} a:hover {{ color: #a3dcc6; }}
    .mono {{ font-family: {MONO}; }}
  </style>
</helmet>
"""
TAIL = "</x-dc>\n</body>\n</html>\n"


def badge(text, color):
    return f'<span class="mono" style="font-size: 9px; padding: 0 4px; border-radius: 3px; border: 1px solid {color}; color: {color}; line-height: 13px;">{text}</span>'


# ───────────────────────── DB schema ─────────────────────────
# (name, [(field, type, badges)], [indexes], note)
TABLES = {
    "folder": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("deleted_at", "TIMESTAMPTZ", []), ("deleted_reason", "VARCHAR(32)", ["CHECK"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("path", "VARCHAR", ["UQ", "NN"]), ("kind", "VARCHAR(32)", ["NN", "CHECK folder_kind"]), ("source", "VARCHAR(32)", ["NN", "CHECK folder_source"]),
                ("first_seen_at", "TIMESTAMPTZ", ["NN"]), ("last_seen_at", "TIMESTAMPTZ", ["NN"])],
               ["CHECK (last_seen_at ≥ first_seen_at)", "CHECK (deleted_at IS NULL) = (deleted_reason IS NULL)"], "папки из [[folders]] конфига"),
    "login_dir": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("deleted_at", "TIMESTAMPTZ", []), ("deleted_reason", "VARCHAR(32)", ["CHECK"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("folder_id", "UUID", ["FK", "NN"]), ("path", "VARCHAR", ["UQ", "NN", "ПДн"]), ("name", "VARCHAR", ["NN"]),
                   ("layout", "VARCHAR(32)", ["NN", "CHECK dir_layout"]), ("first_seen_at", "TIMESTAMPTZ", ["NN"]), ("last_seen_at", "TIMESTAMPTZ", ["NN"])],
                  ["CHECK (last_seen_at ≥ first_seen_at)"], "каталог с .credentials.json"),
    "occupancy": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("login_dir_id", "UUID", ["FK", "NN"]), ("account_id", "UUID", ["FK", "forget → NULL"]),
                   ("token_state", "VARCHAR(32)", ["NN", "CHECK token_state"]), ("started_at", "TIMESTAMPTZ", ["NN"]), ("ended_at", "TIMESTAMPTZ", ["NULL = сейчас"])],
                  ["one open row per login_dir — kept by store, checked by test", "CHECK (ended_at IS NULL OR ended_at ≥ started_at)"],
                  "кто сидел в каталоге когда · журнал"),
    "account": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("deleted_at", "TIMESTAMPTZ", []), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("email", "VARCHAR", ["UQ", "NN", "lower()", "ПДн"]), ("org_name", "VARCHAR", ["ПДн"]), ("org_uuid", "UUID", []),
                 ("subscription_type", "VARCHAR", []), ("rate_limit_tier", "VARCHAR", []), ("color_slot", "TINYINT", ["NN"]),
                 ("first_seen_at", "TIMESTAMPTZ", ["NN"]), ("last_seen_at", "TIMESTAMPTZ", ["NN"])],
                ["CHECK (email = lower(email))"], "учётка = почта · токенов нет"),
    "limit_window": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("deleted_at", "TIMESTAMPTZ", []), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("account_id", "UUID", ["FK", "NN"]), ("kind", "VARCHAR(32)", ["NN", "CHECK window_kind"]),
                      ("model", "VARCHAR", ["NULL кроме scoped"]), ("first_seen_at", "TIMESTAMPTZ", ["NN"]), ("last_seen_at", "TIMESTAMPTZ", ["NN"])],
                     ["UNIQUE (account_id, kind, model)", "CHECK (kind = 'weekly_scoped') = (model IS NOT NULL)"], "измерение: окно лимита учётки"),
    "window_cycle": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("window_id", "UUID", ["FK", "NN"]), ("starts_at", "TIMESTAMPTZ", ["NN"]), ("resets_at", "TIMESTAMPTZ", ["NN"])],
                     ["UNIQUE (window_id, resets_at)", "CHECK (resets_at > starts_at)"], "проход окна: от сброса до сброса"),
    "sample": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("window_id", "UUID", ["FK", "NN"]), ("sampled_at", "TIMESTAMPTZ", ["NN"]), ("cycle_id", "UUID", ["FK", "NN"]), ("percent", "TINYINT", ["0..100"]),
                ("locked", "BOOLEAN", ["NN"]), ("locked_reason", "VARCHAR", []), ("server_severity", "VARCHAR", []), ("is_active", "BOOLEAN", [])],
               ["UNIQUE (window_id, sampled_at) — естественный ключ факта", "zone maps: range by sampled_at"], "замер раз в опрос · ~138k строк / 30 д"),
    "poll": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("account_id", "UUID", ["FK", "NN"]), ("polled_at", "TIMESTAMPTZ", ["NN"]),
              ("outcome", "VARCHAR(32)", ["NN", "CHECK poll_outcome"]), ("http_status", "SMALLINT", []), ("retry_after_sec", "INTEGER", []),
              ("latency_ms", "INTEGER", []), ("error", "VARCHAR", ["≤200, без токенов"])],
             ["no indexes: zone maps by polled_at"], "каждая попытка опроса · журнал"),
    "lock_period": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("window_id", "UUID", ["FK", "NN"]), ("cycle_id", "UUID", ["FK", "NN"]), ("started_at", "TIMESTAMPTZ", ["NN"]),
                     ("ended_at", "TIMESTAMPTZ", ["NULL = идёт"]), ("reason", "VARCHAR", ["…|percent_100"])],
                    ["one open period per window — kept by store", "CHECK (ended_at IS NULL OR ended_at ≥ started_at)"], "интервалы блокировки"),
    "daily_rollup": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("window_id", "UUID", ["FK", "NN"]), ("day_on", "DATE", ["NN", "rollup_tz"]), ("samples", "INTEGER", ["NN"]),
                      ("peak_percent", "TINYINT", ["NN"]), ("avg_percent", "DECIMAL(5,2)", ["NN"]), ("minutes_locked", "INTEGER", ["NN"]), ("resets", "INTEGER", ["NN"])],
                     ["UNIQUE (window_id, day_on)"], "дневные свёртки · 400 д"),
    "config_history": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("source", "VARCHAR(32)", ["NN", "CHECK config_source"]), ("toml", "VARCHAR", ["NN", "token → ***", "ПДн"])],
                       [], "версии файла настроек · 20 шт"),
    "notification": ([("id", "UUID v7", ["PK"]), ("created_at", "TIMESTAMPTZ", ["NN"]), ("updated_at", "TIMESTAMPTZ", ["NN"]), ("deleted_at", "TIMESTAMPTZ", []), ("created_by", "UUID", ["NN", "app"]), ("updated_by", "UUID", ["NN", "app"]), ("account_id", "UUID", ["FK"]), ("window_id", "UUID", ["FK"]),
                      ("kind", "VARCHAR(32)", ["NN", "CHECK notice_kind"]), ("fired_at", "TIMESTAMPTZ", ["NN"]), ("acknowledged_at", "TIMESTAMPTZ", []), ("payload", "JSON", ["только id"])],
                     ["Ф.5, до неё пусто"], "зарезервировано под Ф.5"),
    "schema_meta": ([("key", "VARCHAR", ["PK"]), ("value", "VARCHAR", ["NN"])], ["служебная таблица механизма — без набора §6"], "schema_version, duckdb_version, app_instance_id, rollup_tz, …"),
}
POS = {  # x, y of each card; column width 330
    "folder": (40, 90), "login_dir": (40, 440), "occupancy": (40, 790),
    "account": (430, 90), "limit_window": (430, 460), "window_cycle": (430, 760), "sample": (430, 1000),
    "poll": (820, 90), "lock_period": (820, 460), "daily_rollup": (820, 770),
    "config_history": (1210, 90), "notification": (1210, 330), "schema_meta": (1210, 680),
}
FKS = [  # (child, field, parent)
    ("login_dir", "folder_id", "folder"), ("occupancy", "login_dir_id", "login_dir"), ("occupancy", "account_id", "account"),
    ("poll", "account_id", "account"), ("limit_window", "account_id", "account"), ("sample", "window_id", "limit_window"),
    ("lock_period", "window_id", "limit_window"), ("daily_rollup", "window_id", "limit_window"),
    ("window_cycle", "window_id", "limit_window"), ("sample", "cycle_id", "window_cycle"), ("lock_period", "cycle_id", "window_cycle"),
    ("notification", "account_id", "account"), ("notification", "window_id", "limit_window"),
]
CW, ROW, HEADH, PAD = 330, 17, 30, 8


def card_height(name):
    fields, idx, note = TABLES[name]
    return HEADH + len(fields) * ROW + PAD + (len(idx) * 14 + 6 if idx else 0) + 18


def field_y(name, field):
    fields = TABLES[name][0]
    i = [f[0] for f in fields].index(field)
    return POS[name][1] + HEADH + i * ROW + ROW / 2 + 2


def table_card(name):
    fields, idx, note = TABLES[name]
    x, y = POS[name]
    rows = ""
    for f, t, b in fields:
        bs = " ".join(badge(v, TEAL if v in ("PK",) else VIOLET if v == "FK" else ORANGE if v in ("UQ", "lower()") else RED if v == "ПДн" else AMBER if v in ("forget → NULL", "app") else SUBTLE) for v in b)
        rows += (f'<div style="display: flex; align-items: center; gap: 6px; height: {ROW}px; padding: 0 10px;">'
                 f'<span class="mono" style="font-size: 11px; color: {FG}; min-width: 118px;">{f}</span>'
                 f'<span class="mono" style="font-size: 10px; color: {MUTED}; min-width: 56px;">{t}</span>'
                 f'<span style="display: flex; gap: 4px; flex-wrap: nowrap; overflow: hidden;">{bs}</span></div>')
    idxs = "".join(f'<div class="mono" style="font-size: 9.5px; color: {SUBTLE}; padding: 0 10px; height: 14px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">⌕ {i}</div>' for i in idx)
    return (f'<div style="position: absolute; left: {x}px; top: {y}px; width: {CW}px; background: {SURF}; border: 1px solid {BORDER}; border-radius: 10px; overflow: hidden;">'
            f'<div style="display: flex; align-items: center; justify-content: space-between; height: {HEADH}px; padding: 0 10px; background: {TRACK}; border-bottom: 1px solid {BORDER};">'
            f'<span class="mono" style="font-size: 12px; font-weight: 600;">{name}</span><span style="font-size: 10px; color: {MUTED};">{note}</span></div>'
            f'<div style="padding: 4px 0;">{rows}</div>'
            + (f'<div style="border-top: 1px dashed {BORDER}; padding: 3px 0;">{idxs}</div>' if idx else "")
            + '</div>')


def fk_path(child, field, parent):
    cx, cy = POS[child]
    px, py = POS[parent]
    y1 = field_y(child, field)
    ph = card_height(parent)
    if abs(cx - px) < 10:                       # same column: child below parent → up to parent's bottom
        x = cx + CW / 2 + (20 if field.endswith("account_id") else 0)
        return f"M {x},{cy} C {x},{cy - 40} {x},{py + ph + 40} {x},{py + ph}", (x, py + ph), (x, cy)
    if px > cx:                                  # parent to the right: leave child's right edge, enter parent's left edge
        x1, x2 = cx + CW, px
        y2 = py + HEADH / 2 + (8 if field.endswith("window_id") else 0)
        mid = (x1 + x2) / 2
        return f"M {x1},{y1} C {mid},{y1} {mid},{y2} {x2},{y2}", (x2, y2), (x1, y1)
    x1, x2 = cx, px + CW                         # parent to the left
    y2 = py + HEADH / 2 + (8 if field == "window_id" else 0)
    mid = (x1 + x2) / 2
    return f"M {x1},{y1} C {mid},{y1} {mid},{y2} {x2},{y2}", (x2, y2), (x1, y1)


W, H = 1580, 1400
svg = [f'<svg width="{W}" height="{H}" viewBox="0 0 {W} {H}" style="position: absolute; left: 0; top: 0; pointer-events: none;" aria-hidden="true">'
       f'<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{VIOLET}"></path></marker></defs>']
for child, field, parent in FKS:
    d, head, tail = fk_path(child, field, parent)
    svg.append(f'<path d="{d}" fill="none" stroke="{VIOLET}" stroke-width="1.5" stroke-opacity="0.85" marker-end="url(#arr)"></path>'
               f'<circle cx="{tail[0]:.1f}" cy="{tail[1]:.1f}" r="3" fill="{VIOLET}"></circle>')
svg.append("</svg>")

legend = (f'<div style="position: absolute; left: 40px; top: 24px; display: flex; align-items: center; gap: 18px;">'
          f'<span style="font-size: 16px; font-weight: 600;">claude-limits.duckdb</span>'
          f'<span style="color: {MUTED};">DuckDB v1.5.5 + core_functions + icu (статически) · конвенция БД 2.1: id UUID v7 из приложения, служебный набор у каждой таблицы, *_at TIMESTAMPTZ в UTC, *_on DATE, VARCHAR + CHECK · подплан 01.2 §3</span>'
          f'<span style="display: flex; gap: 6px; align-items: center;">{badge("PK", TEAL)}{badge("FK", VIOLET)}{badge("UQ", ORANGE)}{badge("NN", SUBTLE)}{badge("app = идентичность экземпляра приложения", AMBER)}{badge("ПДн = в реестре 01.2 §10", RED)}'
          f'<span class="mono" style="font-size: 10px; color: {SUBTLE};">⌕ индекс</span>'
          f'<svg width="40" height="10" aria-hidden="true"><circle cx="4" cy="5" r="3" fill="{VIOLET}"></circle><line x1="7" y1="5" x2="30" y2="5" stroke="{VIOLET}" stroke-width="1.5"></line><path d="M 30 1 L 38 5 L 30 9 z" fill="{VIOLET}"></path></svg>'
          f'<span style="font-size: 10px; color: {SUBTLE};">FK → родитель</span></span></div>')

foot = (f'<div style="position: absolute; left: 40px; top: {H - 40}px; color: {SUBTLE}; font-size: 11px;">'
        f'Одно соединение у файбера <span class="mono">store</span>; запись тика — одна транзакция: poll → Appender в stage_sample → sample, lock_period, occupancy, затем CHECKPOINT. '
        f'Ретенция: sample и poll 30 д, daily_rollup 400 д, occupancy и lock_period без срока. Каскадов в DuckDB нет — forget одной транзакцией (01.2 §3.15). Настройки — в claude-limits.toml.</div>')

db_html = (HEAD + f'<div style="position: relative; width: {W}px; height: {H}px; background: {BG}; overflow: hidden;">'
           + legend + "".join(table_card(n) for n in TABLES) + "".join(svg) + foot + "</div>\n" + TAIL)
open("DbSchema.dc.html", "w", encoding="utf-8").write(db_html)
print("DbSchema written", W, H)

# ───────────────────────── API map ─────────────────────────
AW, AH = 1580, 900


def box(x, y, w, h, title, lines, color=BORDER, title_color=FG, bg=SURF):
    body = "".join(f'<div style="font-size: 11px; color: {MUTED}; line-height: 1.45;">{l}</div>' for l in lines)
    return (f'<div style="position: absolute; left: {x}px; top: {y}px; width: {w}px; min-height: {h}px; box-sizing: border-box; padding: 10px 12px; '
            f'background: {bg}; border: 1px solid {color}; border-radius: 10px;">'
            f'<div style="font-weight: 600; font-size: 13px; color: {title_color}; margin-bottom: 4px;">{title}</div>{body}</div>')


def route(x, y, w, method, path, note, color):
    mc = {"GET": TEAL, "POST": ORANGE, "PUT": AMBER, "SSE": VIOLET}[method]
    return (f'<div style="position: absolute; left: {x}px; top: {y}px; width: {w}px; box-sizing: border-box; display: flex; align-items: center; gap: 8px; height: 26px; padding: 0 10px; '
            f'background: {ALT}; border: 1px solid {color}; border-radius: 7px;">'
            f'<span class="mono" style="font-size: 10px; font-weight: 600; color: {mc}; width: 32px;">{method}</span>'
            f'<span class="mono" style="font-size: 11px; color: {FG}; white-space: nowrap;">{path}</span>'
            f'<span style="font-size: 10px; color: {SUBTLE}; margin-left: auto; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{note}</span></div>')


parts = []
parts.append(f'<div style="position: absolute; left: 40px; top: 24px; display: flex; align-items: baseline; gap: 18px;"><span style="font-size: 16px; font-weight: 600;">HTTP API · 127.0.0.1:7391</span>'
             f'<span style="color: {MUTED};">подплан 01.3 · JSON snake_case · время ISO-8601 со смещением · ошибки одним конвертом {{ error: {{ code, message, field, retry_after }} }}</span></div>')

# clients
parts.append(box(40, 80, 260, 96, "Страница в браузере", ["<span class='mono'>GET /</span> + статика из embed_dir", "снимок → SSE → PUT config", "личное — localStorage"]))
parts.append(box(40, 196, 260, 78, "Виджет SDL3 (тот же процесс)", ["читает Snapshot из памяти store", "те же dto, без HTTP"], color=BORDER2))
parts.append(box(40, 294, 260, 96, "Скрипты · curl · дифференциал", ["<span class='mono'>/api/snapshot → таблица</span> ≡ claude_limits.py", "<span class='mono'>/api/export?format=csv</span>", "<span class='mono'>/api/openapi.json</span>"]))
parts.append(box(40, 410, 260, 110, "Телефон в LAN", ["только при <span class='mono'>allow_lan = true</span>", "<span class='mono'>Authorization: Bearer</span> или cookie", "<span class='mono'>GET /?token=…</span> один раз → 303 + Set-Cookie", "10 ошибок/мин → 429 на 60 с"], color=AMBER))

# server column
parts.append(f'<div style="position: absolute; left: 380px; top: 80px; width: 720px; height: 620px; border: 1px dashed {BORDER2}; border-radius: 14px;"></div>')
parts.append(f'<div style="position: absolute; left: 396px; top: 88px; font-size: 13px; font-weight: 600;">Polaris · <span class="mono" style="font-weight: 500; color: {MUTED};">serve_router</span> в spawn · до 64 соединений · тело ≤ 256 КБ</div>')
mw = ["security headers", "access log (без query)", "auth (только при allow_lan)", "routes"]
for i, m in enumerate(mw):
    parts.append(f'<div style="position: absolute; left: {396 + i * 172}px; top: 114px; width: 160px; height: 24px; box-sizing: border-box; display: flex; align-items: center; justify-content: center; '
                 f'background: {TRACK}; border: 1px solid {BORDER}; border-radius: 6px; font-size: 10.5px; color: {SOFT};">{m}{"" if i == 3 else " →"}</div>')

col1, col2 = 396, 750
parts.append(f'<div style="position: absolute; left: {col1}px; top: 152px; font-size: 11px; color: {SUBTLE};">чтение · Cache-Control: no-store</div>')
reads = [("GET", "/api/health", "живость, api_version, пути, размер БД", TEAL), ("GET", "/api/snapshot", "все учётки · forecast · elapsed_share", TEAL),
         ("GET", "/api/history", "range · by=account|folder · step", TEAL), ("GET", "/api/config", "ETag · access_token_set", TEAL),
         ("GET", "/api/export", "CSV/JSON, поток", TEAL), ("GET", "/api/openapi.json", "из типизированных маршрутов", TEAL), ("GET", "/  /assets/*", "index.html · woff2 · ETag", BORDER2)]
for i, r in enumerate(reads):
    parts.append(route(col1, 170 + i * 32, 330, *r))
parts.append(f'<div style="position: absolute; left: {col2}px; top: 152px; font-size: 11px; color: {SUBTLE};">действия</div>')
acts = [("POST", "/api/refresh", "202 · 429 too_soon + Retry-After", ORANGE), ("PUT", "/api/config", "If-Match → 200 · 400 field · 409 · 428", AMBER),
        ("POST", "/api/folders/probe", "kind · login_dirs · problem", ORANGE), ("POST", "/api/config/token", "только loopback · 403 из LAN", ORANGE)]
for i, r in enumerate(acts):
    parts.append(route(col2, 170 + i * 32, 330, *r))
parts.append(f'<div style="position: absolute; left: {col2}px; top: 306px; font-size: 11px; color: {SUBTLE};">поток</div>')
parts.append(route(col2, 324, 330, "SSE", "/api/events", "id: · Last-Event-ID → досылка ≤100 · 32 подписки", VIOLET))
ev = [("snapshot", "после каждого опроса и refresh"), ("config", "после PUT и подхвата файла"), ("folders", "нашли/потеряли каталог"), ("notice", "ошибка конфига, база, listener"), ("ping", "раз в 30 с"), ("bye", "остановка")]
for i, (e, d) in enumerate(ev):
    parts.append(f'<div style="position: absolute; left: {col2 + 14}px; top: {358 + i * 20}px; display: flex; gap: 8px; align-items: baseline;">'
                 f'<span class="mono" style="font-size: 10.5px; color: {VIOLET}; width: 64px;">event: {e}</span><span style="font-size: 10.5px; color: {SUBTLE};">{d}</span></div>')

# errors strip inside server box
errs = ["400 invalid_*", "401 unauthorized", "403 loopback_only", "404 not_found", "405 + Allow", "409 config_changed", "413 range_too_large", "423 config_readonly", "428 precondition_required", "429 too_soon", "503 store_busy", "500 internal + request_id"]
parts.append(f'<div style="position: absolute; left: {col1}px; top: 500px; font-size: 11px; color: {SUBTLE};">коды ошибок</div>')
parts.append(f'<div style="position: absolute; left: {col1}px; top: 518px; width: 688px; display: flex; flex-wrap: wrap; gap: 6px;">'
             + "".join(f'<span class="mono" style="font-size: 10px; color: {SOFT}; padding: 2px 7px; border: 1px solid {BORDER}; border-radius: 5px; background: {ALT};">{e}</span>' for e in errs) + "</div>")
parts.append(f'<div style="position: absolute; left: {col1}px; top: 592px; width: 688px; font-size: 11px; color: {MUTED}; line-height: 1.45;">'
             f'Хендлеры не трогают БД и файлы: запрос/ответ по <span class="mono">Chan</span> к файберу store, таймаут 5 с → 503 store_busy. '
             f'Токены учёток не появляются ни в одном ответе (тест ищет подстроки из фикстур). Заголовки: nosniff · no-referrer · DENY · CSP без внешних источников. CORS выключен.</div>')

# right column: store, storage, pollers, endpoint
parts.append(box(1180, 80, 360, 118, "store · файбер-владелец состояния", ["Snapshot в памяти · подписки SSE", "одно соединение DuckDB (#thread_affine)", "запись тика — одна транзакция", "восстановление снимка из БД при старте"], color=TEAL))
parts.append(box(1180, 220, 360, 92, "claude-limits.duckdb · DuckDB", ["sample · poll · occupancy · lock_period · daily_rollup", "account · limit_window · folder · login_dir", "config_history · notification · schema_meta"], color=BORDER2))
parts.append(box(1180, 334, 360, 92, "claude-limits.toml", ["источник истины настроек · write_atomic", "mtime → перечитать → event: config", "If-Match = хэш файла"], color=BORDER2))
parts.append(box(1180, 448, 360, 96, "поллеры · spawn на учётку", ["HttpClient → api.anthropic.com/api/oauth/usage", "Bearer из .credentials.json (только чтение)", "interval_sec ≥ 60 · 429 → Retry-After · expired → без запроса"], color=ORANGE))
parts.append(box(1180, 566, 360, 74, "обнаружение · раз в тик и по PUT", ["[[folders]] → login_dir → account", "смена почты/токена → occupancy"], color=BORDER2))

# connectors
def line(x1, y1, x2, y2, color=MUTED, dash=""):
    mid = (x1 + x2) / 2
    return f'<path d="M {x1},{y1} C {mid},{y1} {mid},{y2} {x2},{y2}" fill="none" stroke="{color}" stroke-width="1.5" stroke-opacity="0.8" {dash} marker-end="url(#arr2)"></path>'


asvg = [f'<svg width="{AW}" height="{AH}" viewBox="0 0 {AW} {AH}" style="position: absolute; left: 0; top: 0; pointer-events: none;" aria-hidden="true">'
        f'<defs><marker id="arr2" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="{MUTED}"></path></marker></defs>']
for y in (128, 342, 465):                       # clients → server
    asvg.append(line(300, y, 380, y))
asvg.append(line(300, 235, 1180, 139, TEAL, 'stroke-dasharray="4 4"'))   # widget → store directly
asvg.append(line(1100, 200, 1180, 139))                                  # routes → store
asvg.append(line(1100, 340, 1180, 150, VIOLET))                          # SSE ← store
asvg.append(line(1360, 198, 1360, 220, TEAL))                            # store → db
asvg.append(line(1300, 198, 1300, 334, TEAL))                            # store → toml (config write)
asvg.append(line(1440, 448, 1440, 198, ORANGE))                          # pollers → store
asvg.append(line(1240, 566, 1240, 198, MUTED))                           # discovery → store
asvg.append("</svg>")

api_html = (HEAD + f'<div style="position: relative; width: {AW}px; height: {AH}px; background: {BG}; overflow: hidden;">'
            + "".join(parts) + "".join(asvg)
            + f'<div style="position: absolute; left: 40px; top: {AH - 40}px; color: {SUBTLE}; font-size: 11px;">Стрелки: клиенты → маршруты → store; пунктир — виджет читает состояние напрямую, без HTTP. Дифференциал с эталоном сравнивает только email / kind / percent / severity / resets_at.</div>'
            + "</div>\n" + TAIL)
open("ApiMap.dc.html", "w", encoding="utf-8").write(api_html)
print("ApiMap written", AW, AH)
