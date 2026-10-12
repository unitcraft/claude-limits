// Isolated real-Edge/CDP geometry and screenshot evidence. Run from the repo root:
//   node scripts/bar-style-evidence.mjs
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import { join, normalize, extname, resolve } from 'node:path';

const root = process.cwd();
const evidenceDir = join(root, 'docs/reports/assets');
const edge = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].find((p) => process.platform === 'win32' && requireExists(p));
function requireExists(path) {
  try { return !!readFileSyncStat(path); } catch { return false; }
}
function readFileSyncStat(path) {
  // Keep the startup probe synchronous without adding a dependency.
  return process.getBuiltinModule('node:fs').statSync(path);
}
if (!edge) throw new Error('Microsoft Edge executable not found in standard install paths');

const mime = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml' };
const server = createServer(async (req, res) => {
  try {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const path = resolve(root, `.${normalize(pathname)}`);
    if (!path.startsWith(root)) throw new Error('path outside repository');
    const body = await readFile(path);
    res.writeHead(200, { 'content-type': `${mime[extname(path)] || 'application/octet-stream'}; charset=utf-8` });
    res.end(body);
  } catch {
    res.writeHead(404); res.end('not found');
  }
});
server.listen(0, '127.0.0.1');
await new Promise((resolveListen) => server.once('listening', resolveListen));
const port = server.address().port;
const profile = join(process.env.TEMP || process.env.TMP || '.', `claude-limits-edge-bars-${process.pid}`);
const browser = spawn(edge, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-allow-origins=*', '--remote-debugging-port=9222', `--user-data-dir=${profile}`,
  `http://127.0.0.1:${port}/scripts/fixtures/bar-style-evidence.html`,
], { stdio: 'ignore' });

let ws;
try {
  let target;
  for (let i = 0; i < 80; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:9222/json')).json();
      target = list.find((x) => x.type === 'page');
      if (target) break;
    } catch {}
    await delay(250);
  }
  if (!target) throw new Error('Edge CDP page did not become available on port 9222');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolveOpen, reject) => {
    ws.addEventListener('open', resolveOpen, { once: true });
    ws.addEventListener('error', reject, { once: true });
  });
  let nextId = 0;
  const pending = new Map();
  ws.addEventListener('message', (event) => {
    const message = JSON.parse(event.data);
    if (message.id && pending.has(message.id)) {
      const { resolve, reject } = pending.get(message.id);
      pending.delete(message.id);
      message.error ? reject(new Error(message.error.message)) : resolve(message.result);
    }
  });
  const cdp = (method, params = {}) => new Promise((resolveCommand, rejectCommand) => {
    const id = ++nextId;
    pending.set(id, { resolve: resolveCommand, reject: rejectCommand });
    ws.send(JSON.stringify({ id, method, params }));
  });
  const evaluate = async (expression) => {
    const { result, exceptionDetails } = await cdp('Runtime.evaluate', {
      expression, awaitPromise: true, returnByValue: true,
    });
    if (exceptionDetails) throw new Error(exceptionDetails.text || 'Runtime.evaluate failed');
    return result.value;
  };
  await cdp('Page.enable');
  await cdp('Runtime.enable');
  for (let i = 0; i < 80; i++) {
    if (await evaluate("document.body?.dataset.ready === 'true'").catch(() => false)) break;
    await delay(250);
  }
  const hashes = {};
  for (const path of ['src/web/app.css', 'src/web/render.js', 'src/web/format.js', 'scripts/fixtures/bar-style-evidence.html']) {
    hashes[path] = createHash('sha256').update(await readFile(join(root, path))).digest('hex');
  }
  await mkdir(evidenceDir, { recursive: true });
  const screenshot = async (name) => {
    const { data } = await cdp('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    const bytes = Buffer.from(data, 'base64');
    await writeFile(join(evidenceDir, name), bytes);
    return createHash('sha256').update(bytes).digest('hex');
  };
  const initialRoundedShot = await screenshot('30-bars-rounded-before-roundtrips.png');
  const initial = await evaluate('window.runGeometryEvidence ? window.runGeometryEvidence() : null');
  if (!initial?.pass) throw new Error(`browser geometry assertions failed: ${JSON.stringify(initial)}`);
  // Reconstruct a Blocks view at the resized viewport and capture visible geometry.
  const blocks = await evaluate("document.querySelector('#fixture').style.width='450px'; window.setEvidenceStyle('blocks')");
  const blocksShot = await screenshot('30-bars-blocks.png');
  const after = await evaluate("window.runGeometryEvidence()");
  if (!after?.pass) throw new Error(`round-trip assertions failed: ${JSON.stringify(after)}`);
  const roundedShot = await screenshot('30-bars-rounded-after-roundtrips.png');
  await writeFile(join(evidenceDir, '30-bars-edge-evidence.json'), JSON.stringify({
    browser: 'Microsoft Edge headless via CDP', revision: 'task #30; exact source file SHA-256 values are recorded above',
    http: `http://127.0.0.1:${port}/scripts/fixtures/bar-style-evidence.html`,
    hashes, initialRounded: initial, blocks, afterRoundTrips: after,
    screenshots: { initialRounded: initialRoundedShot, blocks: blocksShot, roundedAfterRoundTrips: roundedShot },
  }, null, 2) + '\n');
  console.log(JSON.stringify({ pass: true, hashes, assertions: after.assertions, screenshots: { blocks: blocksShot, rounded: roundedShot } }, null, 2));
} finally {
  try { ws?.close(); } catch {}
  browser.kill();
  server.close();
}
