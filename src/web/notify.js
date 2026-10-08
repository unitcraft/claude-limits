// notify.js — which threshold notifications a snapshot owes (task #9).
//
// Pure: no DOM, no Notification, no localStorage. app.js hands in what it read and
// acts on what comes back, so scripts/test-notify.mjs can judge the rules under node.
//
// THE RULES
//   * thresholds are fixed, 70 and 90 (the release notes' numbers);
//   * one notification per (account, window, threshold, reset moment): the key holds
//     `resets_at`, so a window that reset is a new window and arms again;
//   * a jump over both thresholds gives ONE notification, the higher -- the lower one
//     is marked as told, otherwise it would fire on the next snapshot;
//   * a locked window is not announced (the default decision; it is already shown);
//   * switched off, it says nothing AND records nothing, so switching it on later
//     reports what is still true instead of what was silently swallowed.
export const THRESHOLDS = [70, 90];
const KEEP_MS = 86400_000;      // a told window is forgotten a day after its reset

const keyOf = (l, t) => `${l.account_id}|${l.kind}|${l.model || ''}|${l.resets_at}|${t}`;

/**
 * @param limits   snapshot.limits
 * @param told     { key: resets_at ms } read from localStorage
 * @param opts     { enabled, now, names: {account_id: display name} }
 * @returns { fire: [{key, threshold, title, body}], told }  -- `told` is a new object
 */
export function planNotifications(limits, told, { enabled = false, now = Date.now(), names = {} } = {}) {
  const next = {};
  for (const [k, v] of Object.entries(told || {})) if (v > now - KEEP_MS) next[k] = v;
  if (!enabled) return { fire: [], told: next };

  const fire = [];
  for (const l of limits || []) {
    const pct = Number(l.percent);
    if (l.locked || !l.resets_at || !Number.isFinite(pct)) continue;
    const end = Date.parse(l.resets_at);
    if (Number.isNaN(end)) continue;
    const crossed = THRESHOLDS.filter((t) => pct >= t);
    if (!crossed.length) continue;
    const top = crossed[crossed.length - 1];
    const fresh = crossed.some((t) => !next[keyOf(l, t)]);
    for (const t of crossed) next[keyOf(l, t)] = end;
    if (!fresh) continue;
    const who = names[l.account_id] || 'account';
    fire.push({
      key: keyOf(l, top),
      threshold: top,
      title: `${who}: ${l.label || l.kind} at ${Math.floor(pct)}%`,
      body: `passed ${top}%` + (l.reset_label ? ` · resets ${l.reset_label}` : ''),
    });
  }
  return { fire, told: next };
}
