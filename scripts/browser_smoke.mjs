// Optional local verification with an already-installed Chrome. No npm dependencies/downloads.
// Synthetic data is intercepted in browser memory only; production JSON stays empty.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(import.meta.dirname, '..');
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
assert.ok(existsSync(chrome), 'This optional smoke test requires an already-installed Chrome.');
const cache = resolve(root, '.cache/browser-smoke');
mkdirSync(cache, { recursive: true });
const processChrome = spawn(chrome, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--disable-component-update', '--disable-sync',
  '--disable-extensions', '--disable-breakpad', '--disable-crash-reporter',
  '--disable-domain-reliability', '--metrics-recording-only',
  '--remote-debugging-port=0', `--user-data-dir=${cache}/profile`,
  `--disk-cache-dir=${cache}/disk`, 'about:blank',
], { stdio: 'ignore', env: { ...process.env, TMPDIR: resolve(root, '.cache/tmp'),
  XDG_CACHE_HOME: cache, CHROME_CONFIG_HOME: cache } });
let socket;
let nextId = 0;
const requests = new Map();
const runtimeErrors = [];
let intercept = false;
const original = JSON.parse(readFileSync(resolve(root, 'site/data/events.json'), 'utf8'));
const at = '2026-01-03T00:00:00Z';
const makeRow = (id, area, name) => ({
  event_id: id, is_fixture: false, context_notice: original.context_notice,
  reported_fact: { event_date: '2026-01-02', area, district: null,
    establishment_name: name, establishment_type: null,
    reported_observation: 'Synthetic inspection fixture.', reported_action: 'Samples collected.',
    reported_quantity: null, reported_authority: null, legal_finding_status: 'unknown', formal_finding: null,
    evidence: { reported_observation: { source_url: 'https://example.org/fixture', quote: 'Synthetic inspection fixture.' } } },
  derived_context: { derived_menu_category: 'unknown', derived_owner_category: 'unknown',
    derived_geography: null, action_category: 'other', derived_context_sources: [],
    derived_context_method: 'Synthetic fixture only; no contextual inference.', derived_confidence: 'unknown' },
  sources: [{ source_url: 'https://example.org/fixture', source_title: 'Synthetic browser fixture — not a real article',
    source_publisher: 'Synthetic publisher', source_date: null, source_type: 'official', tier: 'A',
    retrieved_at: at, evidence_quote: 'Synthetic inspection fixture.', evidence_context: 'Synthetic inspection fixture.', text_sha256: 'a'.repeat(64) }],
  verification_status: 'SOURCE VERIFIED', verification_notes: 'Synthetic test only.',
  review: { reviewer: 'fixture', reviewed_at: at, note: 'Synthetic browser test.', all_fields_supported: true, source_context_checked: true },
  llm: { llm_used: false }, record_created_at: at, record_updated_at: at, pipeline_version: '0.1.0',
  history: [{ at, status: 'SOURCE VERIFIED', note: 'Synthetic browser fixture.' }],
});
const fixtureRows = [makeRow('WBFS-aaaaaaaaaaaa', 'Example Area', '<img src=x onerror=alert(1)>'), makeRow('WBFS-bbbbbbbbbbbb', 'Another Area', 'Synthetic Kitchen')];
const fixtureData = { ...original, record_count: 2, records: fixtureRows };

function command(method, params = {}) {
  const id = ++nextId;
  return new Promise((resolvePromise, reject) => {
    const timer = setTimeout(() => { requests.delete(id); reject(new Error(`Timeout: ${method}`)); }, 10000);
    requests.set(id, { resolve: result => { clearTimeout(timer); resolvePromise(result); }, reject });
    socket.send(JSON.stringify({ id, method, params }));
  });
}
async function evaluate(expression) {
  const result = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error('Browser evaluation failed');
  return result.result.value;
}
async function waitFor(expression) {
  for (let i = 0; i < 50; i++) {
    if (await evaluate(expression)) return;
    await delay(100);
  }
  throw new Error(`Condition not reached: ${expression}`);
}
async function screenshot(name) {
  const result = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  writeFileSync(resolve(cache, name + '.png'), Buffer.from(result.data, 'base64'));
}
try {
  const portFile = resolve(cache, 'profile/DevToolsActivePort');
  for (let i = 0; i < 100 && !existsSync(portFile); i++) await delay(100);
  assert.ok(existsSync(portFile), 'Chrome did not expose its local debugging port.');
  const port = readFileSync(portFile, 'utf8').split('\n')[0];
  const pages = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
  socket = new WebSocket(pages.find(p => p.type === 'page').webSocketDebuggerUrl);
  await new Promise((done, reject) => { socket.onopen = done; socket.onerror = reject; });
  socket.onmessage = async ({ data }) => {
    const message = JSON.parse(data);
    if (message.id) {
      const pending = requests.get(message.id);
      if (!pending) return;
      requests.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message)); else pending.resolve(message.result);
    }
    if (message.method === 'Runtime.exceptionThrown') runtimeErrors.push(message.params.exceptionDetails.text);
    if (message.method === 'Fetch.requestPaused') {
      const { requestId, request } = message.params;
      if (intercept && new URL(request.url).pathname === '/data/events.json') {
        await command('Fetch.fulfillRequest', { requestId, responseCode: 200,
          responseHeaders: [{ name: 'Content-Type', value: 'application/json' }],
          body: Buffer.from(JSON.stringify(fixtureData)).toString('base64') });
      } else await command('Fetch.continueRequest', { requestId });
    }
  };
  await command('Page.enable'); await command('Runtime.enable');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await command('Page.navigate', { url: 'http://127.0.0.1:8000/' });
  await waitFor("document.getElementById('metric-events')?.textContent === '0'");
  assert.equal(await evaluate("document.getElementById('empty-evidence').hidden"), false);
  assert.equal(await evaluate("document.querySelector('.status-strip').textContent.includes('Inclusion is not a finding of wrongdoing')"), true);
  await screenshot('zero-desktop');
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true);
  await screenshot('zero-mobile');
  for (const page of ['disclaimer', 'methodology', 'corrections', 'data']) {
    const response = await fetch(`http://127.0.0.1:8000/${page}.html`);
    assert.equal(response.status, 200);
    assert.ok((await response.text()).includes('Inclusion is not a finding of wrongdoing'));
  }
  intercept = true;
  await command('Fetch.enable', { patterns: [{ urlPattern: '*data/events.json*' }] });
  await command('Page.addScriptToEvaluateOnNewDocument', { source: `document.addEventListener('DOMContentLoaded', () => { const b = document.createElement('div'); b.textContent = 'SYNTHETIC BROWSER TEST — NOT PRODUCTION DATA'; b.className = 'notice'; document.body.prepend(b); });` });
  await command('Page.navigate', { url: 'http://127.0.0.1:8000/' });
  await waitFor("document.getElementById('metric-events')?.textContent === '2'");
  assert.equal(await evaluate("document.querySelectorAll('#evidence-rows tr').length"), 2);
  assert.equal(await evaluate("document.querySelectorAll('#evidence-rows img').length"), 0);
  await evaluate("document.querySelector('#chart-areas button').click()");
  assert.equal(await evaluate("document.querySelectorAll('#evidence-rows tr').length"), 1);
  assert.equal(await evaluate("document.querySelector('#evidence-rows td:last-child a').rel"), 'noopener noreferrer');
  assert.equal(await evaluate("document.getElementById('filter-explanation').textContent.includes('1 published records')"), true);
  await evaluate("document.getElementById('clear-filter').click()");
  assert.equal(await evaluate("document.querySelectorAll('#evidence-rows tr').length"), 2);
  await evaluate("document.getElementById('search').value='Another Area'; document.getElementById('search').dispatchEvent(new Event('input'))");
  assert.equal(await evaluate("document.querySelectorAll('#evidence-rows tr').length"), 1);
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await screenshot('synthetic-filter');
  await command('Page.navigate', { url: 'http://127.0.0.1:8000/?event=WBFS-aaaaaaaaaaaa' });
  await waitFor("document.getElementById('record-detail')?.hidden === false");
  assert.equal(await evaluate("document.querySelectorAll('#record-detail img').length"), 0);
  assert.equal(await evaluate("document.getElementById('record-detail').textContent.includes('SOURCE VERIFIED means')"), true);
  assert.equal(await evaluate("document.getElementById('record-detail').textContent.includes('Inclusion is not a finding of wrongdoing')"), true);
  assert.deepEqual(runtimeErrors, []);
  assert.equal(JSON.parse(readFileSync(resolve(root, 'data/events.json'), 'utf8')).record_count, 0);
  console.log('Browser smoke passed: desktop/mobile zero state, policy pages, fixture rendering, chart/search filters, source links, XSS text handling, stable detail URL; no runtime exceptions.');
  console.log('Screenshots: .cache/browser-smoke/{zero-desktop,zero-mobile,synthetic-filter}.png');
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    try { await command('Browser.close'); } catch { /* Browser closes its transport. */ }
    socket.close();
  }
  processChrome.kill('SIGTERM');
}
