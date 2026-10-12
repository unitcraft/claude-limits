// Browser-level proof for Blocks geometry using the shipped render and format modules.
// Run with: node scripts/test-cells-browser.mjs
// Uses installed Edge headless; writes synthetic-only screenshots outside the repo.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { readFileSync, mkdirSync } from 'node:fs';
import { join, resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const edge = process.env.EDGE_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const evidence = join(process.env.LOCALAPPDATA || process.env.TEMP || '.', 'Temp', 'opencode', 'claude-limits-31-browser-evidence');
mkdirSync(evidence, { recursive: true });

const page = `<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="/app.css">
<style>body{zoom:var(--test-zoom,1)} #view-cards{display:flex;width:700px}.row-bars{width:342px}</style></head>
<body><script>localStorage.setItem('view','accounts'); localStorage.setItem('bar_style','blocks');
document.body.dataset.barStyle=localStorage.getItem('bar_style')==='blocks'?'cells':'';</script>
<main><section id="view-list"></section><section id="view-cards"></section></main>
<script type="module">
import { renderCards, layoutCells } from '/render.js';
import { cellGeometry } from '/format.js';
const account={id:'synthetic',email:'synthetic@example.test',state:'ok'};
const pcts=[0,1,3,9,15,18,75,76,81,100,18.5,76.25];
const limits=(pct)=>[{account_id:'synthetic',kind:'weekly_all',label:'synthetic quota',percent:pct,
  forecast:{percent_at_reset:Math.min(100,pct+12),severity:'normal'}}];
const failures=[];
function snapshot(pct){document.dispatchEvent(new CustomEvent('snapshot',{detail:{accounts:[account],limits:limits(pct)}}));}
document.addEventListener('snapshot',(e)=>renderCards(e.detail.accounts,e.detail.limits));
function verify(pct,phase){
  const bar=document.querySelector('#view-cards .bar');
  const fill=bar.querySelector('.bar-fill');
  const ghost=bar.querySelector('.bar-ghost');
  const width=bar.parentElement.clientWidth;
  const geometry=cellGeometry(width,pct,Math.min(100,pct+12));
  const expected=geometry.fillWidth+'px';
  if(fill.style.width!==expected) failures.push(phase+' '+pct+'%: fill '+fill.style.width+', expected '+expected);
  if(fill.dataset.percent!==String(Math.max(0,Math.min(100,pct)))) failures.push(phase+' '+pct+'%: canonical percent lost');
  if(getComputedStyle(fill).backgroundImage.includes('%')) failures.push(phase+': usage mask is scaled by percentage');
  if(!/8px.*10px/.test(getComputedStyle(fill).backgroundImage)) failures.push(phase+': missing fixed 8/2px cell mask');
  if(ghost && geometry.ghostWidth>0 && (ghost.style.left!==geometry.ghostFrom+'px'||ghost.style.width!==geometry.ghostWidth+'px'))
    failures.push(phase+' '+pct+'%: forecast overlay geometry mismatch');
  if(geometry.cells && geometry.filledCells>0 && (parseFloat(fill.style.width)+2)%10!==0)
    failures.push(phase+' '+pct+'%: usage ends off the 10px grid');
  if(bar.getAttribute('aria-valuenow')!==String(Math.round(pct))) failures.push(phase+' '+pct+'%: accessible value changed');
}
window.runProof=()=>{
  if(localStorage.getItem('bar_style')!=='blocks'||document.body.dataset.barStyle!=='cells')
    failures.push('saved Blocks preference was not restored at initial page load');
  if(new URLSearchParams(location.search).get('capture')==='before'){
    snapshot(3); verify(3,'initial screenshot'); return;
  }
  snapshot(3); verify(3,'initial');
  for(const zoom of [1,1.25,1.5,2]){
    document.body.style.setProperty('--test-zoom',String(zoom));
    for(const pct of pcts){ snapshot(pct); verify(pct,'update zoom='+zoom); }
    // Repeated layout must be idempotent and not reinterpret CSS pixels as percent.
    snapshot(81); layoutCells(); verify(81,'repeat-layout zoom='+zoom);
  }
  document.body.style.setProperty('--test-zoom','1');
  snapshot(81); verify(81,'final screenshot');
  document.body.dataset.testResult=failures.length?JSON.stringify(failures):'PASS';
  document.body.dataset.dpr=String(window.devicePixelRatio);
  document.body.dataset.testWidths=Array.from(document.querySelectorAll('.bar-fill')).map(x=>x.style.width).join(',');
};
window.addEventListener('load',()=>setTimeout(window.runProof,100));
</script></body></html>`;

const webRoot = join(root, 'src', 'web');
const server = createServer((req, res) => {
  const pathname = new URL(req.url, 'http://127.0.0.1').pathname;
  if (pathname === '/proof.html') {
    res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); res.end(page); return;
  }
  const leaf = pathname.slice(1);
  if (!['app.css', 'render.js', 'format.js'].includes(leaf)) { res.writeHead(404); res.end(); return; }
  res.writeHead(200, { 'content-type': leaf.endsWith('.css') ? 'text/css' : 'text/javascript' });
  res.end(readFileSync(join(webRoot, leaf)));
});

await new Promise((ok) => server.listen(0, '127.0.0.1', ok));
const runEdge = (args) => new Promise((ok, fail) => {
  const child = spawn(edge, args, { windowsHide: true });
  let stdout = '', stderr = '';
  child.stdout.setEncoding('utf8').on('data', (s) => { stdout += s; });
  child.stderr.setEncoding('utf8').on('data', (s) => { stderr += s; });
  const timeout = setTimeout(() => child.kill(), 60_000);
  child.on('error', fail);
  child.on('close', (status) => {
    clearTimeout(timeout);
    if (status !== 0) fail(new Error(`Edge exited ${status}: ${stderr}`));
    else ok({ stdout, stderr });
  });
});
try {
  const url = `http://127.0.0.1:${server.address().port}/proof.html`;
  const common = ['--headless=new', '--no-first-run', '--disable-gpu', '--hide-scrollbars', '--window-size=1600,650',
    '--virtual-time-budget=2500'];
  for (const dpr of [1, 1.25, 1.5, 2]) {
    const result = await runEdge([...common, `--force-device-scale-factor=${dpr}`,
      `--user-data-dir=${join(evidence, `edge-profile-${dpr}`)}`, '--dump-dom', url]);
    const marker = /data-test-result="([^"]*)"/.exec(result.stdout);
    const actualDpr = /data-dpr="([^"]*)"/.exec(result.stdout);
    assert.ok(marker, `browser did not publish its result at DPR ${dpr}`);
    assert.equal(marker[1], 'PASS', `browser failures at DPR ${dpr}: ${marker[1]}`);
    assert.ok(actualDpr, `browser did not publish DPR ${dpr}`);
    assert.equal(Number(actualDpr[1]), dpr, `Edge DPR requested ${dpr}, got ${actualDpr[1]}`);
  }
  const shotArgs = [...common, '--force-device-scale-factor=1',
    `--user-data-dir=${join(evidence, 'edge-profile-shots')}`];
  await runEdge([...shotArgs, `--screenshot=${join(evidence, 'blocks-before-updates.png')}`, `${url}?capture=before`]);
  await runEdge([...shotArgs, `--screenshot=${join(evidence, 'blocks-after-updates.png')}`, `${url}?capture=after`]);
  console.log(`PASS — actual Edge DOM, render.js + format.js + app.css; values 0/1/3/9/15/18/75/76/81/100 and fractional; CSS zoom and DPR 1/1.25/1.5/2`);
  console.log(`Synthetic screenshots: ${join(evidence, 'blocks-before-updates.png')} and ${join(evidence, 'blocks-after-updates.png')}`);
  console.log('1 passed');
} finally {
  server.close();
}
