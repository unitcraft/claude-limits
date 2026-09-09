// Does the reset caption follow the BACKEND's zone or the viewer's?
//
//   node probes/hunt-conventions-moment-rendering/measure.mjs
//
// THE CONTRACT, quoted from the field that carries it (src/server/dto.nv:206):
//
//     /// IANA zone of the BACKEND, for captions; the page draws axes in the
//     /// browser's zone (§0).
//     tz str
//
// 01.1 line 11: "все примеры времени — в поясе машины, где работает бэкенд".
// 01.1 line 44: reset captions are among the values that come from the backend.
//
// THE DEFECT, until 2026-09-09: `formatResetMoment` called toLocaleTimeString with
// no zone, so the caption rendered wherever the VIEWER happened to be. `tz` arrived
// in every snapshot, was assigned to state.tz, and was read by nothing. A viewer
// three hours from the backend read the reset time three hours wrong, with nothing
// on screen to say so.
//
// This probe pins the caption to a zone explicitly and checks the two things that
// matter: that the zone is obeyed, and that two different zones give two different
// captions -- because a function ignoring its argument also "passes" a test that
// only checks one zone.
import { formatResetMoment, formatReset } from '../../src/web/format.js';

const iso = '2026-09-09T20:50:00Z';                 // 20:50 UTC
const now = Date.parse('2026-09-09T19:48:00Z');

const utc = formatResetMoment(iso, now, 'UTC');
const moscow = formatResetMoment(iso, now, 'Europe/Moscow');       // UTC+3 -> 23:50
const tokyo = formatResetMoment(iso, now, 'Asia/Tokyo');           // UTC+9 -> next day
const none = formatResetMoment(iso, now, null);                    // the viewer's zone

console.log('instant            :', iso);
console.log('caption in UTC     :', JSON.stringify(utc));
console.log('caption in Moscow  :', JSON.stringify(moscow));
console.log('caption in Tokyo   :', JSON.stringify(tokyo));
console.log('caption, no zone   :', JSON.stringify(none), '(this machine)');
console.log('full, UTC          :', JSON.stringify(formatReset(iso, now, 'UTC')));

let bad = 0;
const check = (cond, msg) => { if (!cond) { console.log('  FAIL:', msg); bad = 1; } };

check(utc === '20:50', `UTC caption should be 20:50, got ${JSON.stringify(utc)}`);
check(moscow === '23:50', `Moscow caption should be 23:50, got ${JSON.stringify(moscow)}`);

// My first version of this assertion was WRONG and the probe said so: at that
// instant `now` and `at` both fall on 10 September in Tokyo, so a bare hh:mm is
// correct there. Kept as a note because it is the point of probing -- the wrong
// expectation was mine, not the code's.
//
// The real cross-midnight case: same day in UTC, different days in Tokyo. If the
// "same day" question is asked in the VIEWER's zone instead of the target's, this
// one comes back bare and wrong.
{
  const n2 = Date.parse('2026-09-09T14:00:00Z');    // 23:00 JST, 9 Sep
  const a2 = '2026-09-09T16:00:00Z';                // 01:00 JST, 10 Sep
  const inUtc = formatResetMoment(a2, n2, 'UTC');
  const inTokyo = formatResetMoment(a2, n2, 'Asia/Tokyo');
  console.log('cross-midnight UTC :', JSON.stringify(inUtc), ' Tokyo:', JSON.stringify(inTokyo));
  check(inUtc === '16:00', `same day in UTC, expected bare 16:00, got ${JSON.stringify(inUtc)}`);
  check(/[A-Za-z]/.test(inTokyo),
        `next day in Tokyo, the caption should name the day, got ${JSON.stringify(inTokyo)}`);
}

// The one that catches a function ignoring its argument.
check(new Set([utc, moscow, tokyo]).size === 3,
      'three zones produced fewer than three captions — the zone is being ignored');

// The countdown is local and must stay local: 62 minutes from `now`, in every zone.
for (const z of ['UTC', 'Europe/Moscow', 'Asia/Tokyo']) {
  const full = formatReset(iso, now, z);
  check(full.includes('1h 02m') || full.includes('62m'),
        `countdown should be the same everywhere, got ${JSON.stringify(full)} for ${z}`);
}

console.log(bad ? '\nFAILED' : '\nOK: the caption follows the backend zone, the countdown stays local');
if (bad) process.exit(bad);

// ---- the door, exercised the way the page uses it -------------------------
//
// Everything above passes the zone explicitly, which tests the FUNCTION. The page
// never does that: it calls setCaptionZone once when a snapshot arrives and then
// renders rows with no zone argument anywhere. If that path is broken, everything
// above still passes -- which is how the original defect survived a file full of
// green tests.
{
  const fmt = await import('../../src/web/format.js');

  fmt.setCaptionZone('Europe/Moscow');
  const viaDoor = fmt.formatResetMoment(iso, now);   // no zone argument, as render.js calls it
  fmt.setCaptionZone('UTC');
  const viaDoor2 = fmt.formatResetMoment(iso, now);
  fmt.setCaptionZone(null);

  console.log('');
  console.log('via the page door, Moscow :', JSON.stringify(viaDoor));
  console.log('via the page door, UTC    :', JSON.stringify(viaDoor2));

  if (viaDoor !== '23:50' || viaDoor2 !== '20:50') {
    console.log('  FAIL: the page path ignores setCaptionZone --',
                JSON.stringify(viaDoor), JSON.stringify(viaDoor2));
    process.exit(1);
  }
  if (fmt.getCaptionZone() !== null) {
    console.log('  FAIL: setCaptionZone(null) did not clear');
    process.exit(1);
  }
  console.log('OK: a caption rendered with no zone argument follows the page zone');
}

// ---- every caption, not just the reset one --------------------------------
//
// Closing a class at one call site is not closing the class. A grep for
// toLocaleTimeString / toLocaleDateString / toLocaleString found ten more, and each
// had to be classified by hand: plan 01 par.3.4 says ready-made captions are in the
// backend's zone and CHART AXES are in the browser's. So the axes in chart.js are
// deliberately left alone, and the captions go through captionTime.
//
// This block checks the shared helpers, because "the reset caption is fixed" was
// true an hour before the header clock still showed the viewer's time.
{
  const fmt = await import('../../src/web/format.js');
  const instant = '2026-09-09T20:50:00Z';

  fmt.setCaptionZone('UTC');
  const utcT = fmt.captionTime(instant);
  const utcDT = fmt.captionDateTime(instant);
  fmt.setCaptionZone('Europe/Moscow');
  const mskT = fmt.captionTime(instant);
  const mskDT = fmt.captionDateTime(instant);
  fmt.setCaptionZone(null);

  console.log('');
  console.log('captionTime     UTC / MSK :', JSON.stringify(utcT), '/', JSON.stringify(mskT));
  console.log('captionDateTime UTC / MSK :', JSON.stringify(utcDT), '/', JSON.stringify(mskDT));

  let bad2 = 0;
  const chk = (c, m) => { if (!c) { console.log('  FAIL:', m); bad2 = 1; } };

  chk(utcT === '20:50', `captionTime in UTC should be 20:50, got ${JSON.stringify(utcT)}`);
  chk(mskT === '23:50', `captionTime in Moscow should be 23:50, got ${JSON.stringify(mskT)}`);
  chk(utcT !== mskT, 'captionTime ignores the zone');
  chk(utcDT !== mskDT, 'captionDateTime ignores the zone');
  chk(fmt.captionTime('not a date') === '', 'a bad input should give an empty caption, not "Invalid Date"');

  // The footer string the spec quotes verbatim (01.1 line 72): "polling every 300 s
  // and next 19:52". It must follow the zone too -- it is a caption.
  fmt.setCaptionZone('UTC');
  const footUtc = fmt.footerRight(300, instant);
  fmt.setCaptionZone('Europe/Moscow');
  const footMsk = fmt.footerRight(300, instant);
  fmt.setCaptionZone(null);
  // Not guarded by a "if the export exists" check any more: the first version of
  // this probe looked for footerLeft, did not find it, and printed "skipped". A
  // skipped check reads like a passed one in a green log. The name is footerRight.
  console.log('footer UTC / MSK          :', JSON.stringify(footUtc), '/', JSON.stringify(footMsk));
  chk(footUtc !== footMsk, 'the next-poll caption ignores the zone');
  chk(/20:50/.test(footUtc), 'the UTC footer should name 20:50, got ' + JSON.stringify(footUtc));

  if (bad2) { console.log('\nFAILED'); process.exit(1); }
  console.log('OK: the shared caption helpers follow the page zone');
}
