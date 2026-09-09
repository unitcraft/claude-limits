# -*- coding: utf-8 -*-
"""Serve the browser page against FIXTURES, so it can be looked at before the backend exists.

    python scripts/preview.py          # then open http://127.0.0.1:7392/

WHAT THIS IS NOT, and the distinction matters more than the tool:

  * NOT the product. The real backend is `src/server/` in Nova; this is thirty lines
    of Python that answers three URLs from files on disk.
  * NOT a test. Nothing here asserts anything. The page's actual acceptance is
    `node scripts/check-web.mjs` -- 220 tests that run it in jsdom and check geometry,
    states and captions. Looking at it proves nothing that those do not.
  * NOT a substitute for phase 2. `/api/events` is answered with a single comment and
    left open, so the page settles into `polling` instead of `live`. Refresh and probe
    return the shapes the page needs to not fall over, not the shapes the spec fixes.

WHY IT EXISTS ANYWAY: the page is written and green, and until the backend links there
is no way to SEE it. An artboard shows what it should look like; this shows what it
does look like, which is a different question.

The page is loaded as ES modules (`<script type="module">`), so `file://` cannot open
it -- module loading is origin-checked. That is the whole reason a server is needed
rather than a wrapper page.
"""
import http.server
import json
import os
import pathlib
import socketserver

ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB = ROOT / "src" / "web"
FIX = ROOT / "fixtures" / "api"
PORT = int(os.environ.get("PREVIEW_PORT", "7392"))

# URL -> the fixture that answers it. Everything else under /api is a 404 with a
# problem+json body, because the page is built to expect that shape and silently
# returning {} would teach it a lie.
ROUTES = {
    "/api/snapshot": FIX / "snapshot-mixed.json",
    "/api/config": FIX / "config.json",
    "/api/history": FIX / "history-7d.json",
}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(WEB), **kw)

    def log_message(self, fmt, *args):
        print("  %s" % (fmt % args))

    def _json(self, code, payload, extra=None):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        if path == "/api/events":
            # An open stream with nothing on it: the page will show `polling` and keep
            # retrying, which is honest -- there is no store to publish from.
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            try:
                self.wfile.write(b": preview server, no events\n\n")
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                pass
            return

        if path in ROUTES:
            f = ROUTES[path]
            if not f.exists():
                self._json(500, {"title": "fixture missing", "detail": str(f)})
                return
            payload = json.loads(f.read_text(encoding="utf-8"))
            self._json(200, payload, {"ETag": '"preview"'})
            return

        if path.startswith("/api"):
            self._json(404, {"type": "about:blank", "title": "not in the preview",
                             "status": 404, "code": "not_found", "instance": path})
            return

        if path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        # refresh and probe: enough shape that the page does not fall over.
        if self.path.startswith("/api/snapshot/refresh"):
            self._json(202, {"queued": 0, "wait_for": "snapshot"})
            return
        self._json(404, {"title": "not in the preview", "status": 404,
                         "code": "not_found", "instance": self.path})

    def do_PUT(self):
        self._json(412, {"title": "the preview does not write", "status": 412,
                         "code": "precondition_failed", "instance": self.path})


if __name__ == "__main__":
    missing = [str(p) for p in ROUTES.values() if not p.exists()]
    if missing:
        print("FIXTURES MISSING -- the preview would serve errors:")
        for m in missing:
            print("   ", m)
        raise SystemExit(1)
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", PORT), Handler) as httpd:
        print("preview on http://127.0.0.1:%d/  (fixtures, not the backend)" % PORT)
        print("serving %s" % WEB)
        httpd.serve_forever()
