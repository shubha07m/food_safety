// Optional local verification with an already-installed Chrome. No npm dependencies/downloads.
// Synthetic data is intercepted in browser memory only; production JSON is not modified.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { existsSync, mkdirSync, mkdtempSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';

const root = resolve(import.meta.dirname, '..');
const chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
assert.ok(existsSync(chrome), 'This optional smoke test requires an already-installed Chrome.');
const cache = resolve(root, '.cache/browser-smoke');
mkdirSync(cache, { recursive: true });
const profile = mkdtempSync(resolve(cache, 'profile-'));
const processChrome = spawn(chrome, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--disable-background-networking', '--disable-component-update', '--disable-sync',
  '--disable-extensions', '--disable-breakpad', '--disable-crash-reporter',
  '--disable-domain-reliability', '--metrics-recording-only',
  '--remote-debugging-port=0', `--user-data-dir=${profile}`,
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
  display_summary: `Source reports an inspection involving ${name} in ${area}.`,
  reported_fact: { event_date: '2026-01-02', area, district: null,
    establishment_name: name, establishment_type: null,
    reported_observation: 'Synthetic inspection fixture.', reported_action: 'Samples collected.',
    reported_quantity: null, reported_authority: null, legal_finding_status: 'unknown', formal_finding: null,
    evidence: { reported_observation: { source_url: 'https://example.org/fixture', quote: 'Synthetic inspection fixture.' } } },
  derived_context: { normalized_area: area, action_category: 'not reported',
    action_category_source: null, action_category_method: null, action_category_confidence: 'unknown', action_category_reviewed: false,
    establishment_context: 'unknown', establishment_context_source: null, establishment_context_method: null,
    establishment_context_confidence: 'unknown', establishment_context_reviewed: false,
    menu_context: 'unknown', menu_context_source: null, menu_context_method: null, menu_context_confidence: 'unknown', menu_context_reviewed: false,
    business_format: 'unknown', business_format_source: null, business_format_method: null, business_format_confidence: 'unknown', business_format_reviewed: false,
    derived_context_sources: [], derived_context_method: 'Synthetic fixture only; no contextual inference.', derived_confidence: 'unknown' },
  sources: [{ source_url: 'https://example.org/fixture', source_title: 'Synthetic browser fixture — not a real article',
    source_publisher: 'Synthetic publisher', source_date: null, source_type: 'official', tier: 'A',
    retrieved_at: at, evidence_quote: 'Synthetic inspection fixture.', evidence_context: 'Synthetic inspection fixture.', text_sha256: 'a'.repeat(64) }],
  verification_status: 'SOURCE VERIFIED', verification_notes: 'Synthetic test only.',
  review: { reviewer: 'fixture', reviewed_at: at, note: 'Synthetic browser test.', all_fields_supported: true, source_context_checked: true },
  llm: { llm_used: false }, record_created_at: at, record_updated_at: at, pipeline_version: '0.2.0',
  history: [{ at, status: 'SOURCE VERIFIED', note: 'Synthetic browser fixture.' }],
});
const fixtureRows = [makeRow('WBFS-aaaaaaaaaaaa', 'Example Area', '<img src=x onerror=alert(1)>'), makeRow('WBFS-bbbbbbbbbbbb', 'Another Area', 'Synthetic Kitchen')];
fixtureRows[0].publication_status = 'active_with_warning';
fixtureRows[0].last_successful_evidence_check_at = at;
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
  throw new Error(`Condition not reached: ${expression}; errors: ${JSON.stringify(runtimeErrors)}`);
}
async function screenshot(name) {
  const result = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  writeFileSync(resolve(cache, name + '.png'), Buffer.from(result.data, 'base64'));
}
async function publicScreenshot(path) {
  if (process.env.FOOD_UPDATE_PREVIEWS !== '1') return;
  const result = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  writeFileSync(resolve(root, path), Buffer.from(result.data, 'base64'));
}
try {
  const portFile = resolve(profile, 'DevToolsActivePort');
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
    if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') runtimeErrors.push(message.params.args.map(arg => arg.description || arg.value));
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
  await waitFor(`document.getElementById('metric-events')?.textContent === '${original.record_count}'`);
  await waitFor("document.getElementById('lifecycle-summary') !== null");
  assert.equal(await evaluate("document.getElementById('phase1-help').textContent.includes('Submission form coming shortly')"), true);
  await publicScreenshot('docs/assets/dashboard_preview.png');
  await evaluate("document.querySelector('.map-panel').scrollIntoView({block:'start'})");
  await screenshot('map-desktop');
  await evaluate("window.scrollTo(0,0)");
  assert.equal(await evaluate("document.querySelectorAll('.basemap-outline').length"), 2);
  assert.equal(await evaluate("document.querySelectorAll('#chart-map g[role=button]').length > 0"), true);
  const originalQuote = original.records[0].sources[0].evidence_quote;
  await command('Page.navigate', { url: `http://127.0.0.1:8000/?lang=bn&event=${original.records[0].event_id}` });
  await waitFor("document.getElementById('record-detail')?.hidden === false");
  assert.equal(await evaluate("document.documentElement.lang"), 'bn');
  assert.equal(await evaluate("document.getElementById('patterns-heading').textContent"), 'প্রতিবেদনের তথ্যচিত্র');
  assert.equal(await evaluate("document.querySelector('#record-detail blockquote').textContent"), originalQuote);
  await waitFor("document.getElementById('phase1-help')?.textContent.includes('নথির উৎস কীভাবে যাচাই করা হয়')");
  assert.equal(await evaluate("document.querySelector('.record-link').href.includes('lang=bn')"), true);
  await screenshot('bengali-detail');
  await command('Emulation.setDeviceMetricsOverride', { width: 1200, height: 630, deviceScaleFactor: 1, mobile: false });
  await command('Page.navigate', { url: 'http://127.0.0.1:8000/assets/social-preview.svg' });
  await waitFor("document.documentElement.tagName === 'svg'");
  await publicScreenshot('site/assets/social-preview.png');
  await command('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false });
  await command('Page.navigate', { url: 'http://127.0.0.1:8000/' });
  await waitFor(`document.getElementById('metric-events')?.textContent === '${original.record_count}'`);
  assert.equal(await evaluate("document.getElementById('empty-evidence').hidden"), original.record_count > 0);
  assert.equal(await evaluate("document.querySelector('.status-strip').textContent.includes('Inclusion is not a finding of wrongdoing')"), true);
  await screenshot('zero-desktop');
  await command('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 1, mobile: true });
  assert.equal(await evaluate('document.documentElement.scrollWidth <= window.innerWidth'), true);
  await screenshot('zero-mobile');
  for (const page of ['disclaimer', 'methodology', 'corrections', 'data', 'contribute']) {
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
  assert.equal(await evaluate("document.querySelectorAll('#evidence-rows .source-warning').length"), 1);
  assert.equal(await evaluate("document.querySelectorAll('#evidence-rows img').length"), 0);
  await evaluate("document.querySelector('#chart-areas g[role=button]').dispatchEvent(new MouseEvent('click'))");
  assert.equal(await evaluate("document.querySelectorAll('#evidence-rows tr').length"), 1);
  assert.equal(await evaluate("document.querySelector('#evidence-rows td:last-child a').rel"), 'noopener noreferrer');
  assert.equal(await evaluate("document.getElementById('filter-explanation').textContent.includes('Area')"), true);
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
  assert.equal(JSON.parse(readFileSync(resolve(root, 'data/events.json'), 'utf8')).record_count, original.record_count);
  console.log('Browser smoke passed: desktop/mobile dataset state, policy pages, fixture rendering, chart/search filters, source links, XSS text handling, stable detail URL; no runtime exceptions.');
  console.log('Screenshots: .cache/browser-smoke/{zero-desktop,zero-mobile,synthetic-filter}.png');
} finally {
  if (socket?.readyState === WebSocket.OPEN) {
    try { await command('Browser.close'); } catch { /* Browser closes its transport. */ }
    socket.close();
  }
  processChrome.kill('SIGTERM');
}
