// folders.js — the statistics view grouped by folder (task T2.24).
//
// A folder is a person's seat: over a month the accounts sitting in it change, and
// this view is the HISTORY OF THE SEAT, stitched from the histories of whoever held
// it. Subplan 01.1 §7.
//
// It reuses renderChart and the chart geometry rather than growing a second charting
// path — the only differences are that lines are coloured by account instead of by
// model, and that an occupancy strip is painted under them. Both arrive as options.
import { BOX, occupancySegments, accountColors } from './chart.js';
import { renderChart, attachValuesTable } from './stats.js';
import { formatDuration } from './format.js';
import { el } from './render.js';

/** Segments of the occupancy journal belonging to one folder, oldest first. */
export function occupancyOf(history, folderId) {
  return (history.occupancy || [])
    .filter((o) => o.login_dir_id === folderId)
    .sort((a, b) => Date.parse(a.from) - Date.parse(b.from));
}

/**
 * The series of one folder, split into the three columns of §7.3. Each series is a
 * SEGMENT of one account with its own from/to (01.3 §3.6), so the line breaks at a
 * handover for free: after a switch it is a different series, not a jump in the same
 * one. That is the whole reason the flat shape was chosen over the nested sketch —
 * see the amendment in 01.1 §7.4.
 */
export function columnsOfFolder(series, rangeKind = '30d') {
  const of = (kind) => series.filter((s) => s.kind === kind)
    .slice()
    .sort((a, b) => Date.parse(a.from) - Date.parse(b.from));

  // Per model, the FIRST model of each account is solid and the second dashed (§7.3),
  // so two models of one account are told apart without a second colour.
  const scoped = of('weekly_scoped');
  const seenByAccount = new Map();
  const perModel = scoped.map((s) => {
    const seen = seenByAccount.get(s.account_id) || [];
    if (!seen.includes(s.model)) seen.push(s.model);
    seenByAccount.set(s.account_id, seen);
    return { ...s, dashed: seen.indexOf(s.model) > 0 };
  });

  // THE TITLE PROMISED AN AGGREGATION THAT DID NOT EXIST. The column has always been
  // captioned "session · daily peaks", and the raw points went straight through --
  // 01.1 par.7.3 asks for the maximum of `session.percent` per calendar day, plotted
  // at noon, "otherwise 24 h x 30 blur into noise".
  //
  // At `30 d` that is the difference between thirty readable points and about eight
  // thousand overlapping ones. A caption that describes work nobody did is worse than
  // no caption: it tells the reader the noise IS the peaks.
  //
  // Only at `30 d`. At shorter periods the raw samples are the point, and the title
  // says which is being shown rather than claiming peaks either way.
  const sessionDaily = rangeKind === '30d';
  return [
    {
      key: 'session',
      title: sessionDaily ? 'session · daily peaks' : 'session · 24 h',
      series: sessionDaily ? of('session').map(dailyPeaks) : of('session'),
    },
    { key: 'weekly_all', title: 'all models · 7 d', series: of('weekly_all') },
    { key: 'per_model', title: 'per model · 7 d', series: perModel },
  ];
}

/**
 * One point per calendar day, the day's maximum, placed at noon (01.1 par.7.3).
 *
 * NOON, not the moment the peak happened: the point stands for the whole day, and
 * putting it where the maximum fell would make a day whose peak came at 23:50 look
 * like it belonged to the next one. A regular spacing is also what makes thirty of
 * them read as a series rather than as scatter.
 *
 * The day is taken in UTC. Local days would need the backend's zone here, and the
 * boundary would shift under a reader in another one -- the same instant landing in
 * two different days depending on who is looking. [M-folder-peaks-day-boundary]
 */
export function dailyPeaks(series) {
  const byDay = new Map();
  for (const pt of (series.points || [])) {
    const t = Date.parse(pt.at);
    if (Number.isNaN(t)) continue;
    const day = new Date(t).toISOString().slice(0, 10);
    const prev = byDay.get(day);
    if (!prev || pt.percent > prev.percent) byDay.set(day, pt);
  }
  const points = [...byDay.entries()]
    .sort((a, b) => (a[0] < b[0] ? -1 : 1))
    .map(([day, pt]) => ({ ...pt, at: `${day}T12:00:00Z` }));
  return { ...series, points };
}

/** The `now:` line of a folder card (§7.3). */
export function nowLine(folder, segments) {
  if (folder.now && folder.now.email) {
    return { text: `now: ${folder.now.email} · since ${shortDay(folder.now.since)}`, tone: null };
  }
  const last = [...segments].reverse().find((s) => s.email);
  if (!last) return { text: 'no login in this period', tone: 'warning' };
  const why = last.token_state && last.token_state !== 'ok' ? ` · ${reason(last.token_state)}` : '';
  return { text: `no login since ${shortDay(last.to)}${why}`, tone: 'warning' };
}

const reason = (state) => (state === 'stale' ? 'token expired' : state);

/**
 * The model drawn dashed in the per-model column, if there is one (01.1 par.7.1).
 *
 * The same rule columnsOfFolder uses -- the second distinct model in arrival order --
 * because the legend has to name the line the chart actually dashes, and deriving it
 * twice by two rules is how they come to disagree.
 */
export function secondModelOf(history) {
  const seen = [];
  for (const s of (history && history.series) || []) {
    if (s.kind !== 'weekly_scoped' || !s.model) continue;
    if (!seen.includes(s.model)) seen.push(s.model);
  }
  return seen.length > 1 ? seen[1] : null;
}

function shortDay(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
}

/**
 * The occupancy strip above the charts (§7.3): 22 px, the full width of the three
 * columns, one block per stretch. A block wider than 46 px carries the account name
 * inside it; a narrower one would truncate to nothing legible, so it carries only the
 * tooltip — which every block has regardless.
 */
/** 01.1 par.7.3: a segment narrower than this holds no label. */
const LABEL_MIN_PX = 46;

/**
 * The strip's assumed rendered width, in CSS pixels.
 *
 * NOT MEASURED. It is app.css's 900 px breakpoint, borrowed. See the note at the use
 * site: measuring is the right answer and needs a relayout pass this view does not
 * have. [M-folder-label-threshold-measured]
 */
const ASSUMED_STRIP_PX = 900;

export function renderOccupancy(segments, colors) {
  const strip = el('div', 'occupancy');
  strip.setAttribute('role', 'img');
  strip.setAttribute('aria-label', occupancyLabel(segments));
  for (const seg of segments) {
    const block = el('div', 'occ-block');
    block.style.left = `${(seg.x / BOX.w) * 100}%`;
    block.style.width = `${(seg.width / BOX.w) * 100}%`;
    if (seg.email) {
      block.style.setProperty('--occ', colors.get(seg.email) || 'var(--series-1)');
      // 46 px of the strip, as a share of its width: the block is positioned in per
      // cent because the strip stretches, and the threshold has to stretch too.
      //
      // WHERE 900 COMES FROM, and why it is a guess. 01.1 par.7.3 says the label
      // appears "if the segment is wider than 46 px" -- 46 REAL pixels, which needs
      // the strip's rendered width, and this code runs before the strip is in the
      // document. So it assumes 900, and 900 is not measured: it is the media-query
      // breakpoint from app.css:492, borrowed because it was a number to hand.
      //
      // What that costs: above 900 px the strip is wider than assumed and the
      // threshold triggers too early -- labels appear in segments narrower than 46 px
      // and get clipped. Below it, they are withheld from segments wide enough to
      // hold them. Neither is visible as a fault; it just looks like the labels were
      // chosen oddly.
      //
      // The real answer is to decide after mounting, the way layoutCells does for the
      // bars -- measure `.occupancy`'s clientWidth and set the labels then. That is a
      // relayout pass this view does not have, and the view itself is blocked on
      // `GET /api/history?by=folder`, so building the pass now would be work nobody
      // can see. Named rather than left as a bare constant.
      // [M-folder-label-threshold-measured]
      if (seg.width / BOX.w > LABEL_MIN_PX / ASSUMED_STRIP_PX) {
        block.textContent = seg.email.split('@')[0] + '@';
      }
    } else {
      block.dataset.empty = 'true';
    }
    block.title = seg.email
      ? `${seg.email} · ${shortStamp(seg.from)} → ${shortStamp(seg.to)} · ${span(seg)}`
      : `no login · ${shortStamp(seg.from)} → ${shortStamp(seg.to)} · ${span(seg)}`;
    strip.append(block);
  }
  return strip;
}

const span = (seg) => formatDuration(Date.parse(seg.to) - Date.parse(seg.from));

function shortStamp(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false });
}

function occupancyLabel(segments) {
  const names = segments.map((s) => s.email || 'no login');
  return `who was logged in: ${names.join(', then ')}`;
}

// ---------------------------------------------------------------- tiles -----

/** The four tiles of §7.2 — different questions from §6.2, so a separate builder. */
export function renderFolderTiles(tiles) {
  const box = el('div', 'tiles');
  const t = tiles || {};

  const tile = (label, value, note, tone) => {
    const n = el('div', 'tile');
    n.append(el('div', 'tile-label', label));
    const v = el('div', 'tile-value', value);
    if (tone) v.dataset.tone = tone;
    n.append(v);
    n.append(el('div', 'tile-note', note));
    return n;
  };

  const busiest = t.busiest_folder;
  box.append(tile('Login switches · 30 d',
    t.switches == null ? '—' : String(t.switches),
    busiest && busiest.chain
      ? `${busiest.name}: ${busiest.chain.map((e) => e.split('@')[0]).join(' → ')}`
      : (t.switches == null ? 'no history yet' : 'no folder changed hands'),
    null));

  box.append(tile('Locked while in a folder',
    t.locked_seconds ? formatDuration(t.locked_seconds * 1000) : (t.locked_seconds === 0 ? '0m' : '—'),
    t.locked_seconds ? (t.locked_email || 'across the folders below') : 'nobody was locked',
    t.locked_seconds ? 'critical' : null));

  box.append(tile('Folder with most logins',
    busiest ? busiest.name : '—',
    busiest && busiest.chain ? `${busiest.chain.length} different logins` : 'no history yet',
    null));

  const dry = t.days_without_login;
  box.append(tile('Days without a login',
    dry ? String(dry.days) : '—',
    dry ? `${dry.folder ? dry.folder.name : 'a folder'} · ${reason(dry.reason === 'token_expired' ? 'stale' : dry.reason)}` : 'every folder had one',
    dry && dry.days > 0 ? 'warning' : null));

  return box;
}

// ----------------------------------------------------------------- card -----

export function renderFolderCard(folder, history, colors, rangeKind) {
  const range = history.range;
  const card = el('section', 'folder-card');
  card.dataset.folder = folder.name || folder.id;

  const head = el('div', 'stat-head');
  head.append(el('div', 'folder-name', folder.name || 'folder'));
  // The path is a fact about the machine and is null over LAN (01.3 §3.3); showing
  // an empty element there would read as a bug rather than as a redaction.
  if (folder.path) head.append(el('div', 'folder-path', folder.path));
  const segments = occupancySegments(occupancyOf(history, folder.id), range);
  const now = nowLine(folder, segments);
  const line = el('div', 'stat-summary', now.text);
  if (now.tone) line.dataset.tone = now.tone;
  head.append(line);
  card.append(head);

  card.append(renderOccupancy(segments, colors));

  const backdrop = segments.map((s) => ({
    x: s.x, width: s.width, email: s.email,
    color: s.email ? (colors.get(s.email) || 'var(--series-1)') : null,
  }));

  const series = (history.series || []).filter((s) => s.login_dir_id === folder.id);
  const cols = el('div', 'stat-cols');
  for (const column of columnsOfFolder(series, rangeKind)) {
    const c = el('div', 'stat-col');
    c.dataset.column = column.key;
    c.append(el('div', 'col-title', column.title));
    c.append(renderChart(column.series, range, {
      backdrop,
      noFill: true,                 // the backdrop is the fill here (§7.3)
      colorOf: (s) => colors.get(s.email) || null,
      rangeKind,
      label: `${column.title}, folder ${folder.name}`,
    }));
    c.append(el('div', 'col-now', folderCaption(column)));
    cols.append(c);
  }
  card.append(cols);
  // Labelled by ACCOUNT here: in a folder the same window belongs to whoever held it,
  // and a column headed `session 5h` three times would say nothing.
  attachValuesTable(card, series,
    (x) => `${x.email || '?'} ${x.model || x.kind}`);
  return card;
}

function folderCaption(column) {
  const live = column.series.filter((s) => !s.to);
  const source = live.length ? live : column.series.slice(-1);
  const parts = [];
  for (const s of source) {
    const last = s.points && s.points.length ? s.points[s.points.length - 1] : null;
    if (!last) continue;
    const who = s.email ? s.email.split('@')[0] : '?';
    parts.push(column.key === 'per_model'
      ? `${who} ${s.model} ${last.percent}%`
      : `${who} ${last.percent}%`);
  }
  return parts.join(' · ') || 'no data';
}

// ----------------------------------------------------------------- view -----

export function renderFolders(history, rangeKind = '30d') {
  const view = document.getElementById('view-stats');
  if (!view) return;
  view.replaceChildren();

  const folders = (history && history.folders) || [];
  if (!history || !history.range || !folders.length) {
    view.append(el('p', 'placeholder', 'no folder history yet'));
    return;
  }

  view.append(renderFolderFilters(rangeKind, history));
  // The limitation, stated on the page and not only in the plan (§7.4): a number the
  // reader could misread is worse than one they cannot see.
  if (history.note) view.append(el('p', 'view-note', history.note));
  view.append(renderFolderTiles(history.tiles));

  const colors = accountColors(history.occupancy);
  const cards = el('div', 'stat-cards');
  for (const folder of folders) {
    cards.append(renderFolderCard(folder, history, colors, rangeKind));
  }
  view.append(cards);
}

function renderFolderFilters(rangeKind, history) {
  const bar = el('div', 'stats-filters');

  const ranges = el('div', 'range-tabs');
  ranges.setAttribute('role', 'tablist');
  ranges.setAttribute('aria-label', 'period');
  for (const r of ['24h', '7d', '30d']) {
    const b = el('button', 'chip', r === '24h' ? '24 h' : r === '7d' ? '7 d' : '30 d');
    b.setAttribute('type', 'button');
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(r === rangeKind));
    b.dataset.range = r;
    ranges.append(b);
  }
  bar.append(ranges);

  const groups = el('div', 'group-tabs');
  groups.setAttribute('role', 'tablist');
  groups.setAttribute('aria-label', 'grouping');
  for (const g of ['account', 'folder']) {
    const b = el('button', 'chip', g === 'account' ? 'Accounts' : 'Folders');
    b.setAttribute('type', 'button');
    b.setAttribute('role', 'tab');
    b.setAttribute('aria-selected', String(g === 'folder'));
    b.dataset.group = g;
    groups.append(b);
  }
  bar.append(groups);

  // The legend names ACCOUNTS here, not models (§7.1), and includes the grey.
  const legend = el('div', 'legend');
  for (const [email, color] of accountColors(history.occupancy)) {
    const item = el('span', 'legend-item', email);
    item.style.setProperty('--swatch', color);
    legend.append(item);
  }
  const none = el('span', 'legend-item', 'no login');
  none.style.setProperty('--swatch', 'var(--fg-subtle)');
  legend.append(none);

  // THE DASH, 01.1 par.7.1. The legend listed the account colours and the grey, and
  // stopped -- while columnsOfFolder marks the second model of an account `dashed`
  // (line 42) and the chart draws it that way. So a dashed line appeared on screen
  // with nothing anywhere saying what it meant, and the obvious reading of a dash is
  // "estimated" or "no data", neither of which it is.
  //
  // Named from the data rather than hard-coded as `Opus`, which is what the spec's
  // example happens to say: the second model differs per account and per plan, and a
  // legend naming a model nobody uses is worse than one naming none.
  const second = secondModelOf(history);
  if (second) {
    const dash = el('span', 'legend-item', second);
    dash.dataset.dashed = 'true';
    legend.append(dash);
  }
  bar.append(legend);
  return bar;
}
