// Isolated Edge/CDP acceptance for task #27. Serves this checkout's assets and
// synthetic fixtures only; never connects to the installed 7391 service.
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { spawn, spawnSync } from 'node:child_process';
import { setTimeout as delay } from 'node:timers/promises';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const evidence = path.join(root, 'docs/reports/assets/task27');
const port = 19341, debugPort = 19342;
const requests = [];
const json = async (name) => JSON.parse(await readFile(path.join(root, `fixtures/api/${name}`), 'utf8'));
const snapshot = await json('snapshot-mixed.json');
let config = await json('config.json');
const hashes = {};
const server = createServer(async (req, res) => {
  requests.push(`${req.method} ${req.url}`);
  const url = new URL(req.url, `http://127.0.0.1:${port}`);
  if (url.pathname === '/api/health') return send(res, { api_version: 'synthetic-task27' });
  if (url.pathname === '/api/config') {
    if (req.method === 'PUT') {
      let body = '';
      for await (const chunk of req) body += chunk;
      const patch = JSON.parse(body);
      if (patch.ui?.accounts_order) {
        config = structuredClone(config);
        config.config.ui.accounts_order = patch.ui.accounts_order;
        const order = new Map(patch.ui.accounts_order.map((email, i) => [email, i]));
        snapshot.accounts.sort((a, b) => (order.get(a.email) ?? 999) - (order.get(b.email) ?? 999));
      }
      res.setHeader('ETag', '"synthetic-updated"');
      return send(res, { etag: '"synthetic-updated"', config: config.config, applied: {} });
    }
    res.setHeader('ETag', config.etag);
    return send(res, config);
  }
  if (url.pathname === '/api/snapshot') return send(res, snapshot);
  if (url.pathname === '/api/history') return send(res, await json('history-7d.json'));
  if (url.pathname === '/api/events') {
    res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache' });
    res.write(': synthetic mock stream\n\n');
    return;
  }
  const rel = url.pathname === '/' ? '/index.html' : url.pathname;
  const file = path.resolve(root, 'src/web', `.${decodeURIComponent(rel)}`);
  if (!file.startsWith(path.resolve(root, 'src/web') + path.sep)) { res.writeHead(404).end(); return; }
  try {
    const bytes = await readFile(file);
    hashes[rel.slice(1)] = createHash('sha256').update(bytes).digest('hex');
    res.writeHead(200, { 'content-type': file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.svg') ? 'image/svg+xml' : 'text/html' });
    res.end(bytes);
  } catch { res.writeHead(404).end(); }
});
function send(res, value) { res.writeHead(200, { 'content-type': 'application/json' }); res.end(JSON.stringify(value)); }

const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const profile = await import('node:fs/promises').then(({ mkdtemp }) => mkdtemp(path.join(os.tmpdir(), 'task27-edge-')));
let edge;
try {
  await mkdir(evidence, { recursive: true });
  await new Promise((resolve, reject) => server.listen(port, '127.0.0.1', (e) => e ? reject(e) : resolve()));
  edge = spawn(edgePath, ['--headless=new', '--disable-gpu', '--no-first-run', '--disable-sync',
    '--no-default-browser-check', '--remote-allow-origins=*', `--remote-debugging-port=${debugPort}`,
    `--user-data-dir=${profile}`, `http://127.0.0.1:${port}/`], { stdio: 'ignore' });
  let target;
  for (let i = 0; i < 80; i++) {
    try { target = (await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json()).find((x) => x.type === 'page'); if (target) break; } catch {}
    await delay(250);
  }
  assert.ok(target?.webSocketDebuggerUrl, 'Edge CDP page becomes available');
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let id = 0;
  const pending = new Map();
  ws.onmessage = ({ data }) => {
    const msg = JSON.parse(data);
    if (msg.id && pending.has(msg.id)) { pending.get(msg.id)(msg); pending.delete(msg.id); }
  };
  const cdp = (method, params = {}) => new Promise((resolve, reject) => {
    const call = ++id;
    pending.set(call, (msg) => msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result));
    ws.send(JSON.stringify({ id: call, method, params }));
  });
  const evaluate = async (expression) => {
    const result = await cdp('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (result.exceptionDetails) throw new Error(result.exceptionDetails.text);
    return result.result.value;
  };
  await cdp('Page.enable'); await cdp('Runtime.enable'); await delay(900);
  for (const legacy of ['list', 'cards']) {
    await evaluate(`localStorage.setItem('view', ${JSON.stringify(legacy)}); location.reload()`);
    await delay(500);
    assert.equal(await evaluate(`localStorage.getItem('view')`), 'accounts', `${legacy} preference migrates`);
    assert.equal(await evaluate(`document.querySelector('#view-cards').hidden`), false, `${legacy} opens the unified screen`);
  }
  const baseline = await evaluate(`({legacy:localStorage.getItem('view'), list:!!document.querySelector('#view-list'), cards:!!document.querySelector('#view-cards'), accounts:document.querySelector('#view-cards').hidden, handle:!!document.querySelector('.card-handle'), reorder:document.querySelector('[data-action=reorder]').textContent.trim()})`);
  assert.equal(baseline.list, false); assert.equal(baseline.cards, true); assert.equal(baseline.handle, false);
  await cdp('Page.captureScreenshot').then(async (x) => writeFile(path.join(evidence, 'task27-ordinary.png'), Buffer.from(x.data, 'base64')));
  await evaluate(`document.querySelector('[data-action=reorder]').click()`);
  const active = await evaluate(`({label:document.querySelector('[data-action=reorder]').textContent.trim(), pressed:document.querySelector('[data-action=reorder]').getAttribute('aria-pressed'), handle:!!document.querySelector('.card-handle')})`);
  assert.deepEqual(active, { label: 'Done', pressed: 'true', handle: true });
  await evaluate(`document.querySelector('[data-view=stats]').click()`);
  assert.equal(await evaluate(`document.querySelector('[data-action=reorder]').textContent.trim()`), 'Reorder');
  assert.equal(await evaluate(`!!document.querySelector('.card-handle')`), false);
  await evaluate(`document.querySelector('[data-view=accounts]').click(); document.querySelector('[data-action=reorder]').click()`);
  await cdp('Page.captureScreenshot').then(async (x) => writeFile(path.join(evidence, 'task27-reorder.png'), Buffer.from(x.data, 'base64')));
  const browserDragOrder = await evaluate(`(() => {
    const cards = Array.from(document.querySelectorAll('#view-cards > .card'));
    const handle = cards[0].querySelector('.card-handle');
    handle.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, button: 0 }));
    const transfer = new DataTransfer();
    cards[0].dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: transfer }));
    const rect = cards[2].getBoundingClientRect();
    cards[2].dispatchEvent(new DragEvent('dragover', { bubbles: true, clientY: rect.bottom + 1, dataTransfer: transfer }));
    cards[2].dispatchEvent(new DragEvent('drop', { bubbles: true, clientY: rect.bottom + 1, dataTransfer: transfer }));
    return Array.from(document.querySelectorAll('#view-cards > .card')).map((x) => x.dataset.email);
  })()`);
  assert.notDeepEqual(browserDragOrder, ['main@example.com', 'heavy@example.com', 'ops@example.org', 'qa@example.org'],
    'the in-mode browser drag path changes account order');
  await delay(200);
  await evaluate(`document.querySelector('.card-handle').focus()`);
  for (const key of [' ', 'ArrowDown', ' ']) {
    await cdp('Input.dispatchKeyEvent', { type: 'keyDown', key, code: key === ' ' ? 'Space' : key });
    await cdp('Input.dispatchKeyEvent', { type: 'keyUp', key, code: key === ' ' ? 'Space' : key });
  }
  await delay(200);
  const persistedOrder = await evaluate(`Array.from(document.querySelectorAll('#view-cards > .card')).map((x) => x.dataset.email)`);
  assert.equal(persistedOrder.length, 4);
  assert.ok(requests.some((x) => x === 'PUT /api/config'), 'keyboard drop persists using the existing config endpoint');
  await evaluate(`document.querySelector('[data-action=reorder]').click()`);
  assert.equal(await evaluate(`!!document.querySelector('.card-handle')`), false);
  await evaluate(`document.querySelector('[data-view=stats]').click()`);
  assert.equal(await evaluate(`document.querySelector('#view-stats').hidden`), false);
  await evaluate(`document.querySelector('[data-view=accounts]').click()`);
  assert.equal(await evaluate(`document.querySelector('#view-cards').hidden`), false);
  await evaluate(`document.querySelector('[data-action=settings]').click()`);
  await delay(200);
  assert.equal(await evaluate(`!!document.querySelector('[data-path="ui.view"]')`), false);
  await evaluate(`document.querySelector('[data-action=cancel]').click()`);
  await evaluate(`location.reload()`); await delay(800);
  assert.equal(await evaluate(`!!document.querySelector('.card-handle')`), false);
  assert.deepEqual(await evaluate(`Array.from(document.querySelectorAll('#view-cards > .card')).map((x) => x.dataset.email)`), persistedOrder,
    'the persisted server order survives reload');
  await cdp('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  const mobile = await evaluate(`({width:innerWidth, documentWidth:document.documentElement.scrollWidth, cards:document.querySelectorAll('#view-cards > .card').length})`);
  assert.ok(mobile.documentWidth <= mobile.width, `390px viewport has no horizontal overflow: ${JSON.stringify(mobile)}`);
  const result = {
    baseline, active,
    browserDragOrder,
    mobile,
    legacyMigration: await evaluate(`localStorage.getItem('view')`),
    afterReloadHandles: await evaluate(`document.querySelectorAll('.card-handle').length`),
    assets: hashes,
    mockRequests: requests,
  };
  assert.equal(result.legacyMigration, 'accounts');
  assert.deepEqual(requests.filter((x) => !x.startsWith('GET ')), ['PUT /api/config', 'PUT /api/config'],
    'only the explicit drag/drop and keyboard reorder writes use the existing order endpoint');
  await writeFile(path.join(evidence, 'task27-cdp.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify(result, null, 2));
  ws.close();
} finally {
  if (edge?.pid) spawnSync('taskkill', ['/pid', String(edge.pid), '/t', '/f'], { stdio: 'ignore' });
  server.close();
}
