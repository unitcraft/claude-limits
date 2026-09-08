// The live-update state machine under a stopped and restarted server (T2.21).
//
//   node scripts/test-live.mjs
//
// The card's acceptance is "with the server stopped the dot is grey and reads
// `polling`; once it starts, green". That is exactly what runs here, with a fake
// stream and a fake clock instead of a real backend: the point of the test is the
// TRANSITIONS and their timing, and a real server can only show one of them per run,
// slowly, and never the interesting ones (five errors in a row, a reconnect that
// fails again, thirty seconds of nothing).
//
// The real module is imported. A transcription would drift from the shipped code,
// which is the whole reason live.js exists as its own file.
import assert from 'node:assert/strict';
import { createLive, silentTooLong, POLL_WHEN_DEGRADED_MS, SSE_RETRY_MS } from '../src/web/live.js';

// ------------------------------------------------------------------ doubles --

/** An EventSource as the HTML spec describes it, including the part that matters:
 *  a failed connection goes back to CONNECTING (0) and fires `error` -- it does NOT
 *  become CLOSED, and the browser keeps retrying on its own schedule. */
class FakeStream {
  constructor(url) {
    this.url = url;
    this.readyState = 0;            // CONNECTING
    this.listeners = {};
    this.closeCalls = 0;
  }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  close() { this.closeCalls += 1; this.readyState = 2; }
  emit(name, data) { for (const fn of this.listeners[name] || []) fn({ data }); }
  serverAccepts() { this.readyState = 1; this.emit('open'); }
  serverRefuses() { this.readyState = 0; this.emit('error'); }
}

function makeClock() {
  let t = 0, nextId = 1;
  const jobs = new Map();
  const add = (fn, ms, every) => { const id = nextId++; jobs.set(id, { at: t + ms, fn, every }); return id; };
  return {
    now: () => t,
    pending: () => jobs.size,
    timers: {
      set: (fn, ms) => add(fn, ms, 0),
      clear: (id) => jobs.delete(id),
      setEvery: (fn, ms) => add(fn, ms, ms),
      clearEvery: (id) => jobs.delete(id),
    },
    advance(ms) {
      const end = t + ms;
      for (;;) {
        let pick = null;
        for (const [id, j] of jobs) if (j.at <= end && (pick === null || j.at < jobs.get(pick).at)) pick = id;
        if (pick === null) break;
        const j = jobs.get(pick);
        t = j.at;
        if (j.every) j.at = t + j.every; else jobs.delete(pick);
        j.fn();
      }
      t = end;
    },
  };
}

/** A page: one dot, one snapshot counter, one event log. */
function makePage({ serverUp = true } = {}) {
  const clock = makeClock();
  const page = {
    clock,
    mode: null,             // what the dot says
    modes: [],              // every mode it has said, in order
    polls: 0,
    events: [],
    streams: [],
    serverUp,
    live: null,
  };
  page.live = createLive({
    openStream: (url) => {
      const s = new FakeStream(url);
      page.streams.push(s);
      // A real EventSource connects asynchronously; a stopped server refuses on the
      // next turn of the loop, not inside the constructor.
      clock.timers.set(() => (page.serverUp ? s.serverAccepts() : s.serverRefuses()), 1);
      return s;
    },
    now: clock.now,
    timers: clock.timers,
    setLive: (m) => { page.mode = m; page.modes.push(m); },
    poll: () => { page.polls += 1; },
    onEvent: (name, data) => page.events.push([name, data]),
  });
  return page;
}

// -------------------------------------------------------------------- tests --

let passed = 0;
const test = (name, fn) => {
  try { fn(); passed++; console.log(`  ok   ${name}`); }
  catch (e) { console.log(`  FAIL ${name}\n       ${e.message}`); process.exitCode = 1; }
};

console.log('the dot, with the server stopped and started (acceptance of T2.21)');

test('server stopped: the dot reads polling', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  assert.equal(p.mode, 'connecting', 'before the first answer it is neither up nor down');
  p.clock.advance(5);
  assert.equal(p.mode, 'polling', 'a refused stream is the grey dot');
});

test('server running: the dot reads live', () => {
  const p = makePage({ serverUp: true });
  p.live.start();
  p.clock.advance(5);
  assert.equal(p.mode, 'live');
  assert.ok(p.live.isOpen());
});

test('stopped, then started: grey, then green, without a reload', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(5);
  assert.equal(p.mode, 'polling');

  p.serverUp = true;                       // the backend comes back
  p.clock.advance(SSE_RETRY_MS + 5);       // and we try again on our own schedule
  assert.equal(p.mode, 'live');
  assert.deepEqual(p.modes, ['connecting', 'polling', 'polling', 'live'],
    'it announces the retry as polling, not as connecting: the page is not fresh');
});

console.log('\ndegraded mode: polling every 10 s (01.3 sec.5)');

test('while down it polls every 10 s, and not more often', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(1);
  assert.equal(p.polls, 0, 'the first poll is one interval away, not immediate');
  p.clock.advance(POLL_WHEN_DEGRADED_MS);
  assert.equal(p.polls, 1);
  p.clock.advance(POLL_WHEN_DEGRADED_MS * 2);
  assert.equal(p.polls, 3);
});

test('five errors in a row still leave ONE poll interval', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(5);
  for (let i = 0; i < 5; i++) p.streams[0].emit('error');
  p.clock.advance(POLL_WHEN_DEGRADED_MS);
  assert.equal(p.polls, 1, 'an unguarded interval per error would poll six times a period');
});

test('polling stops the moment the stream opens', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(POLL_WHEN_DEGRADED_MS + 5);
  assert.equal(p.polls, 1);
  p.serverUp = true;
  p.clock.advance(SSE_RETRY_MS);
  const after = p.polls;
  p.clock.advance(POLL_WHEN_DEGRADED_MS * 3);
  assert.equal(p.polls, after, 'a live stream that also polls asks for everything twice');
});

console.log('\nreconnection: 30 s, ours, and exactly one');

test('the stream is CLOSED on error, which is what puts us on the 30 s schedule', () => {
  // Without the close the browser reconnects on its own timetable (seconds), and
  // the 30 s of 01.3 sec.5 is a number in a document that nothing obeys.
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(5);
  assert.equal(p.streams[0].closeCalls, 1);
  assert.equal(p.streams[0].readyState, 2, 'CLOSED: the browser stops retrying by itself');
});

test('it reconnects after 30 s, not before', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(5);
  assert.equal(p.streams.length, 1);
  p.clock.advance(SSE_RETRY_MS - 10);
  assert.equal(p.streams.length, 1, 'nothing may open early: that is the avalanche sec.17 forbids');
  p.clock.advance(20);
  assert.equal(p.streams.length, 2);
});

test('twenty errors do not queue twenty reconnects', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(5);
  for (let i = 0; i < 20; i++) p.streams[0].emit('error');
  p.clock.advance(SSE_RETRY_MS + 5);
  assert.equal(p.streams.length, 2,
    'one pending reconnect, so one new stream -- not twenty, each with its own error loop');
});

test('a reconnect that fails again waits another full 30 s', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(SSE_RETRY_MS + 5);
  assert.equal(p.streams.length, 2);
  p.clock.advance(SSE_RETRY_MS - 20);
  assert.equal(p.streams.length, 2, 'the backoff does not shrink because we are impatient');
  p.clock.advance(30);
  assert.equal(p.streams.length, 3);
});

test('stop() leaves no timer behind', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(5);
  assert.ok(p.clock.pending() > 0);
  p.live.stop();
  assert.equal(p.clock.pending(), 0, 'a page that navigates away must not keep polling');
});

console.log('\nevents and silence');

test('every named event is handed on and marks the time', () => {
  const p = makePage({ serverUp: true });
  p.live.start();
  p.clock.advance(5);
  const s = p.streams[0];
  p.clock.advance(1000);
  s.emit('snapshot', '{"a":1}');
  s.emit('notice', '{"level":"reload"}');
  s.emit('config', '');
  s.emit('ping', '');
  assert.deepEqual(p.events.map(([n]) => n), ['snapshot', 'notice', 'config', 'ping']);
  assert.equal(p.events[0][1], '{"a":1}', 'the payload travels unparsed: parsing is the page\'s job');
  assert.equal(p.live.lastEvent, p.clock.now());
});

test('an open but silent stream is not proof of life', () => {
  const p = makePage({ serverUp: true });
  p.live.start();
  p.clock.advance(5);
  assert.equal(silentTooLong(p.live, p.clock.now()), false);
  assert.equal(silentTooLong(p.live, p.clock.now() + 89_000), false);
  assert.equal(silentTooLong(p.live, p.clock.now() + 91_000), true);
});

test('a closed stream is never "silent": it is already polling', () => {
  const p = makePage({ serverUp: false });
  p.live.start();
  p.clock.advance(5);
  assert.equal(silentTooLong(p.live, p.clock.now() + 10 * 60_000), false,
    'otherwise a down backend would be polled twice over, by two different rules');
});

test('a constructor that throws lands in the same degraded mode', () => {
  const clock = makeClock();
  let polls = 0, mode = null;
  const live = createLive({
    openStream: () => { throw new Error('blocked by the browser'); },
    now: clock.now,
    timers: clock.timers,
    setLive: (m) => { mode = m; },
    poll: () => { polls += 1; },
    onEvent: () => {},
  });
  live.start();
  assert.equal(mode, 'polling', 'not left on connecting forever');
  clock.advance(POLL_WHEN_DEGRADED_MS);
  assert.equal(polls, 1);
});

console.log(`\n${passed} passed${process.exitCode ? ', SOME FAILED' : ''}`);
