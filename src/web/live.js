// live.js — the SSE transport as a state machine, separated from the page (T2.21).
//
// Why a separate file: the acceptance of T2.21 is "with the server stopped the dot is
// grey and reads `polling`; once it starts, green". That is a statement about a state
// machine, and there is no way to drive it from a test while it sits inside app.js
// tangled with `document`, `fetch` and the real `EventSource`. Everything this module
// touches arrives as a dependency, so `scripts/test-live.mjs` can stop and start a
// fake server and watch the dot.
//
// THE ONE DECISION WORTH READING. On a transport error this closes the stream instead
// of letting the browser reconnect by itself. That looks like extra work and is the
// opposite: an EventSource whose connection fails goes back to CONNECTING and retries
// on its OWN schedule -- a few seconds, or whatever the server last sent in a `retry:`
// field. 01.3 section 5 says reconnection happens after 30 s, and convention section
// 17 explains why the number matters: clients that were all refused at the same moment
// must not all come back at the same moment. While the stream stays open-ish the code
// below cannot honour that number, because its own reconnect timer is guarded by a
// readyState that never becomes CLOSED. Closing hands the schedule back to us.
//
// The page is NOT left silent in the meantime: a closed stream means polling every
// 10 s, which is the degraded mode the same section prescribes.

export const POLL_WHEN_DEGRADED_MS = 10_000;
export const SSE_RETRY_MS = 30_000;
export const SILENCE_LIMIT_MS = 90_000;

/**
 * @param deps.openStream  (url) => EventSource-like: addEventListener, close, readyState
 * @param deps.now         () => epoch ms
 * @param deps.timers      { set, clear, setEvery, clearEvery } — setTimeout & friends
 * @param deps.setLive     (mode) => void, mode is 'live' | 'polling' | 'connecting'
 * @param deps.poll        () => void — fetch one snapshot now
 * @param deps.onEvent     (name, data) => void — 'snapshot' | 'notice' | 'config' | 'ping'
 */
export function createLive(deps) {
  const {
    openStream, now, timers, setLive, poll, onEvent,
    url = '/api/events',
    pollMs = POLL_WHEN_DEGRADED_MS,
    reconnectMs = SSE_RETRY_MS,
  } = deps;

  const self = {
    stream: null,
    lastEvent: 0,
    pollTimer: null,
    reconnectTimer: null,
    opens: 0,          // for tests and for a human reading the console
    attempts: 0,       // 'connecting' is the FIRST attempt only -- see start()
    isOpen: () => self.stream != null && self.stream.readyState === 1,
    start,
    stop,
  };

  function startPolling() {
    // Guarded: `error` can arrive several times, and a second interval would double
    // the request rate at exactly the moment the backend is asking for less.
    if (self.pollTimer == null) self.pollTimer = timers.setEvery(poll, pollMs);
  }

  function stopPolling() {
    if (self.pollTimer != null) { timers.clearEvery(self.pollTimer); self.pollTimer = null; }
  }

  function mark(name) {
    return (e) => { self.lastEvent = now(); onEvent(name, e && e.data); };
  }

  function onError() {
    // Close first -- see the header. After this readyState is CLOSED and the browser
    // has stopped retrying on its own, so the 30 s below is the real schedule.
    if (self.stream) { try { self.stream.close(); } catch { /* already gone */ } }
    self.stream = null;

    setLive('polling');
    startPolling();

    // Exactly one pending reconnect. Without this guard every repeated `error`
    // queues another timer, and thirty seconds later they all build a stream each.
    if (self.reconnectTimer == null) {
      self.reconnectTimer = timers.set(() => {
        self.reconnectTimer = null;
        start();
      }, reconnectMs);
    }
  }

  function start() {
    // Only the very first attempt is 'connecting'. A reconnect happens while the page
    // is already polling and already grey; announcing 'connecting' every 30 s would
    // show movement where there is none.
    setLive(self.attempts === 0 ? 'connecting' : 'polling');
    self.attempts += 1;
    let s;
    try {
      s = openStream(url);
    } catch {
      // The constructor itself threw: no stream to listen to, so drive the same
      // degraded path by hand rather than leaving the page on 'connecting' forever.
      onError();
      return self;
    }
    self.stream = s;

    s.addEventListener('open', () => {
      self.opens += 1;
      self.lastEvent = now();
      setLive('live');
      stopPolling();
      if (self.reconnectTimer != null) { timers.clear(self.reconnectTimer); self.reconnectTimer = null; }
    });
    for (const name of ['snapshot', 'notice', 'config', 'ping']) {
      s.addEventListener(name, mark(name));
    }
    s.addEventListener('error', onError);
    return self;
  }

  function stop() {
    if (self.stream) { try { self.stream.close(); } catch { /* already gone */ } }
    self.stream = null;
    stopPolling();
    if (self.reconnectTimer != null) { timers.clear(self.reconnectTimer); self.reconnectTimer = null; }
  }

  return self;
}

/**
 * An open stream that has said nothing for too long is not proof of life: 01.1 §1.1
 * asks for a snapshot anyway rather than showing an ageing number under a green dot.
 */
export function silentTooLong(live, nowMs, limitMs = SILENCE_LIMIT_MS) {
  return live.isOpen() && nowMs - live.lastEvent > limitMs;
}
