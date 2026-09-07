import { aggregate, dimensions, filterOptions, filterRows, recordDate, safeExternal, validateDataset } from './data.mjs';
import { strings as t } from './strings.mjs';

const $ = id => document.getElementById(id);
const SVG = 'http://www.w3.org/2000/svg';
const state = { rows: [], filters: {}, query: '', repository: null, retired: [] };
const chartNames = {
  timeline: 'Date', areas: 'Area', actions: 'Reported action', establishments: 'Establishment context',
  publishers: 'Publisher', verification: 'Verification status', menus: 'Menu context',
  business_formats: 'Business format',
};

function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function svgNode(tag, attributes = {}, text = null) {
  const element = document.createElementNS(SVG, tag);
  for (const [name, value] of Object.entries(attributes)) element.setAttribute(name, value);
  if (text != null) element.textContent = text;
  return element;
}
function external(label, value) {
  const url = safeExternal(value);
  if (!url) return node('span', 'Source link unavailable');
  const anchor = node('a', label);
  anchor.href = url; anchor.target = '_blank'; anchor.rel = 'noopener noreferrer';
  return anchor;
}
function dateText(value, timestamp = false) {
  if (!value) return t.notReported;
  if (!timestamp) return value;
  const date = new Date(value);
  return Number.isNaN(date.valueOf()) ? t.notReported : `${date.toLocaleString('en-GB', { timeZone: 'UTC' })} UTC`;
}
async function json(path) {
  const response = await fetch(path, { cache: 'no-cache', credentials: 'omit' });
  if (!response.ok) throw new Error('Resource unavailable');
  return response.json();
}
function activate(dimension, value) {
  if (state.filters[dimension] === value) delete state.filters[dimension];
  else state.filters[dimension] = value;
  renderAll();
  $('evidence').scrollIntoView({ behavior: 'auto', block: 'start' });
  $('clear-filter').focus({ preventScroll: true });
}
function interactive(group, dimension, label, count) {
  group.setAttribute('role', 'button'); group.setAttribute('tabindex', '0');
  group.setAttribute('aria-label', `${label}: ${count} records. Show underlying evidence.`);
  group.setAttribute('aria-pressed', String(state.filters[dimension] === label));
  group.addEventListener('click', () => activate(dimension, label));
  group.addEventListener('keydown', event => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); activate(dimension, label); }
  });
}
function emptyChart(container) {
  const empty = node('div', null, 'empty-chart');
  empty.append(node('span', '—', 'empty-dash'), node('p', t.chartEmpty));
  container.append(empty);
}
function horizontalChart(container, entries, dimension, color) {
  container.replaceChildren();
  if (!entries.length) return emptyChart(container);
  const width = 620; const rowHeight = 38; const labelWidth = 205;
  const max = Math.max(...entries.map(([, count]) => count), 1);
  const svg = svgNode('svg', { viewBox: `0 0 ${width} ${entries.length * rowHeight + 8}`, class: `svg-bars ${color}`, 'aria-hidden': 'true' });
  entries.forEach(([label, count], index) => {
    const y = index * rowHeight + 5;
    const group = svgNode('g', { class: state.filters[dimension] === label ? 'selected' : '' });
    interactive(group, dimension, label, count);
    group.append(svgNode('text', { x: 0, y: y + 20, class: 'svg-label' }, label));
    group.append(svgNode('rect', { x: labelWidth, y: y + 7, width: 350, height: 14, rx: 7, class: 'svg-track' }));
    group.append(svgNode('rect', { x: labelWidth, y: y + 7, width: Math.max(4, 350 * count / max), height: 14, rx: 7, class: 'svg-value' }));
    group.append(svgNode('text', { x: 605, y: y + 20, class: 'svg-count', 'text-anchor': 'end' }, count));
    svg.append(group);
  });
  container.append(svg);
}
function timelineChart(entries) {
  const container = $('chart-timeline'); container.replaceChildren();
  if (!entries.length) return emptyChart(container);
  const width = 900; const height = 260; const bottom = 205; const left = 52;
  const max = Math.max(...entries.map(([, count]) => count), 1);
  const slot = (width - left - 25) / entries.length; const barWidth = Math.min(64, slot * .58);
  const svg = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, class: 'svg-timeline coral', 'aria-hidden': 'true' });
  for (let tick = 0; tick <= max; tick += Math.max(1, Math.ceil(max / 4))) {
    const y = bottom - (tick / max) * 160;
    svg.append(svgNode('line', { x1: left, y1: y, x2: width - 15, y2: y, class: 'grid-line' }));
    svg.append(svgNode('text', { x: left - 12, y: y + 4, 'text-anchor': 'end', class: 'axis-label' }, tick));
  }
  entries.forEach(([label, count], index) => {
    const x = left + slot * index + (slot - barWidth) / 2; const barHeight = 160 * count / max;
    const group = svgNode('g', { class: state.filters.timeline === label ? 'selected' : '' });
    interactive(group, 'timeline', label, count);
    group.append(svgNode('rect', { x, y: bottom - barHeight, width: barWidth, height: barHeight, rx: 5, class: 'svg-value' }));
    group.append(svgNode('text', { x: x + barWidth / 2, y: bottom - barHeight - 9, 'text-anchor': 'middle', class: 'svg-count' }, count));
    group.append(svgNode('text', { x: x + barWidth / 2, y: bottom + 22, 'text-anchor': 'middle', class: 'axis-label' }, label.slice(5)));
    svg.append(group);
  });
  svg.append(svgNode('text', { x: width / 2, y: 252, 'text-anchor': 'middle', class: 'axis-title' }, 'Source publication/event date used by the record'));
  container.append(svg);
}
function donutChart(container, entries, dimension, palette) {
  container.replaceChildren();
  if (!entries.length) return emptyChart(container);
  const total = entries.reduce((sum, [, count]) => sum + count, 0);
  const svg = svgNode('svg', { viewBox: '0 0 620 270', class: 'svg-donut', 'aria-hidden': 'true' });
  const circumference = 2 * Math.PI * 72; let offset = 0;
  entries.forEach(([label, count], index) => {
    const length = total ? circumference * count / total : 0;
    const group = svgNode('g', { class: state.filters[dimension] === label ? 'selected' : '' });
    interactive(group, dimension, label, count);
    group.append(svgNode('circle', { cx: 106, cy: 128, r: 72, fill: 'none', stroke: palette[index % palette.length], 'stroke-width': 28, 'stroke-dasharray': `${Math.max(0, length - 2)} ${circumference - Math.max(0, length - 2)}`, 'stroke-dashoffset': -offset, transform: 'rotate(-90 106 128)', class: 'donut-segment' }));
    offset += length;
    const y = 52 + index * 34;
    group.append(svgNode('rect', { x: 222, y: y - 10, width: 10, height: 10, rx: 2, fill: palette[index % palette.length] }));
    group.append(svgNode('text', { x: 243, y, class: 'svg-label' }, label));
    group.append(svgNode('text', { x: 598, y, 'text-anchor': 'end', class: 'svg-count' }, `${count} · ${total ? Math.round(count / total * 100) : 0}%`));
    svg.append(group);
  });
  svg.append(svgNode('text', { x: 106, y: 120, 'text-anchor': 'middle', class: 'donut-total' }, total));
  svg.append(svgNode('text', { x: 106, y: 140, 'text-anchor': 'middle', class: 'axis-label' }, 'records'));
  container.append(svg);
}
function mapChart(rows) {
  const container = $('chart-map'); container.replaceChildren();
  const mapped = rows.filter(row => Number.isFinite(row.derived_context.latitude) && Number.isFinite(row.derived_context.longitude));
  $('map-coverage').textContent = `Map coverage: ${mapped.length} of ${rows.length} records have a reviewed coarse location anchor.`;
  if (!mapped.length) return emptyChart(container);
  const groups = new Map();
  for (const row of mapped) {
    const key = row.derived_context.normalized_area || row.reported_fact.area;
    const current = groups.get(key) || { count: 0, lat: row.derived_context.latitude, lon: row.derived_context.longitude };
    current.count += 1; groups.set(key, current);
  }
  const width = 920; const height = 410; const pad = 42;
  const lats = [...groups.values()].map(point => point.lat); const lons = [...groups.values()].map(point => point.lon);
  const minLat = Math.min(...lats) - .12; const maxLat = Math.max(...lats) + .12;
  const minLon = Math.min(...lons) - .12; const maxLon = Math.max(...lons) + .12;
  const x = lon => pad + (lon - minLon) / (maxLon - minLon || 1) * (width - pad * 2);
  const y = lat => height - pad - (lat - minLat) / (maxLat - minLat || 1) * (height - pad * 2);
  const svg = svgNode('svg', { viewBox: `0 0 ${width} ${height}`, class: 'svg-map', 'aria-hidden': 'true' });
  for (let tick = 0; tick < 5; tick += 1) {
    const gx = pad + tick * (width - pad * 2) / 4; const gy = pad + tick * (height - pad * 2) / 4;
    svg.append(svgNode('line', { x1: gx, y1: pad, x2: gx, y2: height - pad, class: 'map-grid' }), svgNode('line', { x1: pad, y1: gy, x2: width - pad, y2: gy, class: 'map-grid' }));
  }
  for (const [area, point] of groups) {
    const group = svgNode('g', { class: state.filters.areas === area ? 'selected' : '' });
    interactive(group, 'areas', area, point.count);
    group.append(svgNode('circle', { cx: x(point.lon), cy: y(point.lat), r: 7 + point.count * 2, class: 'map-point' }));
    group.append(svgNode('text', { x: x(point.lon) + 11, y: y(point.lat) - 10, class: 'map-label' }, `${area} · ${point.count}`));
    svg.append(group);
  }
  svg.append(svgNode('text', { x: pad, y: height - 10, class: 'axis-title' }, 'Reference coordinate plot based on reviewed OpenStreetMap area anchors'));
  container.append(svg);
}
function coverage(stats) {
  const labels = {
    named_establishment: 'Named establishment', reported_action: 'Reported action',
    reported_quantity: 'Reported quantity', establishment_context: 'Establishment context',
    menu_context: 'Menu context', business_format: 'Business format', cross_source: 'Cross-source verification',
  };
  const entries = Object.entries(stats.coverage);
  const container = $('coverage-chart'); container.replaceChildren();
  const svg = svgNode('svg', { viewBox: `0 0 620 ${entries.length * 42}`, class: 'coverage-svg', role: 'img', 'aria-label': 'Percentage of published records with each field available' });
  entries.forEach(([key, metric], index) => {
    const y = index * 42;
    svg.append(svgNode('text', { x: 0, y: y + 16, class: 'svg-label' }, labels[key]));
    svg.append(svgNode('rect', { x: 230, y: y + 4, width: 300, height: 14, rx: 7, class: 'svg-track' }));
    svg.append(svgNode('rect', { x: 230, y: y + 4, width: 3 * metric.percentage, height: 14, rx: 7, class: 'coverage-value' }));
    svg.append(svgNode('text', { x: 615, y: y + 16, 'text-anchor': 'end', class: 'svg-count' }, `${metric.percentage}%`));
  });
  container.append(svg);
}
function unknowns(stats) {
  const total = stats.total;
  const entries = [
    ['Quantity not reported', total - stats.coverage.reported_quantity.count],
    ['Establishment unnamed', total - stats.coverage.named_establishment.count],
    ['Establishment context unknown', total - stats.coverage.establishment_context.count],
    ['Menu context unknown', total - stats.coverage.menu_context.count],
    ['Business format unknown', total - stats.coverage.business_format.count],
    ['Single-source records', total - stats.coverage.cross_source.count],
  ];
  $('unknown-counts').replaceChildren(...entries.map(([label, count]) => {
    const card = node('div'); card.append(node('strong', count), node('span', label)); return card;
  }));
}
function charts(stats) {
  document.querySelectorAll('.chart-notice').forEach(element => { element.textContent = t.chartNotice; });
  timelineChart(Object.entries(stats.timeline));
  horizontalChart($('chart-areas'), Object.entries(stats.areas).sort((a, b) => b[1] - a[1]), 'areas', 'blue');
  mapChart(state.rows);
  donutChart($('chart-actions'), Object.entries(stats.actions).sort((a, b) => b[1] - a[1]), 'actions', ['#bd624d', '#d58b73', '#a77422', '#426b7c']);
  donutChart($('chart-establishments'), Object.entries(stats.establishments).sort((a, b) => b[1] - a[1]), 'establishments', ['#a77422', '#d9b96e', '#426b7c', '#839fa9', '#bd624d']);
  donutChart($('chart-publishers'), Object.entries(stats.publishers).sort((a, b) => b[1] - a[1]), 'publishers', ['#174f3c', '#3d8271', '#426b7c', '#a77422']);
  donutChart($('chart-verification'), Object.entries(stats.verification), 'verification', ['#174f3c', '#426b7c']);
  donutChart($('chart-menus'), Object.entries(stats.menus), 'menus', ['#a77422', '#d9b96e', '#426b7c', '#839fa9']);
  donutChart($('chart-business_formats'), Object.entries(stats.business_formats), 'business_formats', ['#426b7c', '#6f99aa', '#a77422']);
  coverage(stats); unknowns(stats);
}
function renderFilters() {
  const labels = { timeline: 'Date', areas: 'Area', publishers: 'Publisher', actions: 'Action', establishments: 'Establishment type', verification: 'Status', menus: 'Menu', business_formats: 'Business format' };
  const options = filterOptions(state.rows); const controls = $('filter-controls'); controls.replaceChildren();
  for (const [dimension, label] of Object.entries(labels)) {
    if (!options[dimension]?.length) continue;
    const wrapper = node('label', label); const select = node('select'); select.dataset.dimension = dimension;
    const all = node('option', `All ${label.toLowerCase()}s`); all.value = ''; select.append(all);
    for (const value of options[dimension]) { const option = node('option', value); option.value = value; select.append(option); }
    select.value = state.filters[dimension] || '';
    select.addEventListener('change', event => { if (event.target.value) state.filters[dimension] = event.target.value; else delete state.filters[dimension]; renderAll(); });
    wrapper.append(select); controls.append(wrapper);
  }
}
function renderRows() {
  const rows = filterRows(state.rows, state.filters, state.query);
  $('evidence-rows').replaceChildren();
  $('row-count').textContent = `${rows.length} of ${state.rows.length} published records`;
  const active = Object.entries(state.filters).map(([dimension, value]) => `${chartNames[dimension]} “${value}”`);
  $('filter-explanation').textContent = active.length
    ? `Why am I seeing this number? These rows match ${active.join(' and ')}${state.query ? ' plus the search term' : ''}.`
    : `Why am I seeing this number? ${state.query ? 'Your search matches these published rows.' : 'These are all underlying published records.'}`;
  $('empty-evidence').hidden = rows.length > 0;
  for (const record of rows) {
    const facts = record.reported_fact; const tr = node('tr'); const name = node('td');
    const link = node('a', facts.establishment_name || 'Establishment unnamed', 'record-link');
    link.href = `?event=${encodeURIComponent(record.event_id)}`; name.append(link, node('small', record.event_id));
    for (const text of [dateText(recordDate(record)), facts.area || t.unknown]) tr.append(node('td', text));
    tr.append(name, node('td', record.display_summary), node('td', facts.reported_action || t.notReported), node('td', facts.reported_quantity || t.notReported));
    const status = node('td'); status.append(node('span', record.verification_status, 'badge'));
    const source = node('td'); for (const item of record.sources) source.append(external(`${item.source_publisher} ↗`, item.source_url));
    tr.append(status, source); $('evidence-rows').append(tr);
  }
}
function detailSection(container, label, title) {
  const section = node('section', null, 'detail-section');
  section.append(node('p', label, 'eyebrow'), node('h3', title)); container.append(section); return section;
}
function detail() {
  const id = new URLSearchParams(location.search).get('event'); if (!id) return;
  const container = $('record-detail'); container.hidden = false;
  const back = node('a', '← All published records', 'text-link'); back.href = 'index.html'; container.append(back);
  const record = state.rows.find(row => row.event_id === id);
  if (!record) {
    const retired = state.retired.find(row => row.event_id === id);
    container.append(node('h2', 'Record unavailable'), node('p', retired ? `${retired.event_id} · ${retired.verification_status}. This record is suspended from public statistics.` : 'No published record is available at this address.'), node('p', t.context, 'notice'));
    return;
  }
  const facts = record.reported_fact; const context = record.derived_context;
  container.append(node('p', 'SOURCE-ATTRIBUTED RECORD', 'eyebrow'), node('h2', facts.establishment_name || 'Establishment unnamed'));
  const badges = node('div', null, 'detail-badges'); badges.append(node('span', record.verification_status, 'badge'), node('span', record.sources.length > 1 ? 'MULTI-SOURCE' : 'SINGLE SOURCE', 'badge neutral'));
  container.append(badges, node('p', record.display_summary, 'detail-summary'), node('p', t.context, 'notice'));
  const reported = detailSection(container, 'REPORTED FACTS', 'What the source supports');
  const fields = node('dl', null, 'detail-fields');
  const labels = { event_date: 'Event date', area: 'Reported area', district: 'Reported district', establishment_name: 'Establishment', establishment_type: 'Reported establishment type', reported_observation: 'Source-reported observation', reported_action: 'Reported action', reported_quantity: 'Reported quantity', reported_authority: 'Reported authority', legal_finding_status: 'Formal legal finding status', formal_finding: 'Source-reported formal finding' };
  for (const [key, label] of Object.entries(labels)) {
    fields.append(node('dt', label), node('dd', facts[key] || t.notReported)); const support = facts.evidence[key];
    if (support) { const evidence = node('dd', null, 'field-evidence'); evidence.append(node('q', support.quote), document.createTextNode(' '), external('Supporting source ↗', support.source_url)); fields.append(evidence); }
  }
  reported.append(fields);
  const derived = detailSection(container, 'DERIVED CONTEXT', 'Reviewed contextual metadata');
  derived.append(node('p', t.contextCategory, 'notice'), node('p', `Normalized area: ${context.normalized_area || t.unknown} · Establishment context: ${context.establishment_context} · Action grouping: ${context.action_category} · Menu: ${context.menu_context} · Business format: ${context.business_format}`), node('p', `${context.derived_context_method} Confidence: ${context.derived_confidence}.`));
  const evidenceSection = detailSection(container, 'SOURCE EVIDENCE', 'Read the retained source span');
  for (const source of record.sources) {
    const card = node('article', null, 'source-card');
    card.append(external(source.source_title, source.source_url), node('p', `${source.source_publisher} · Tier ${source.tier} · Publication date: ${dateText(source.source_date)} · Retrieved: ${dateText(source.retrieved_at, true)}`), node('blockquote', source.evidence_quote), node('p', `Evidence context: ${source.evidence_context}`), node('small', `Extracted-text SHA-256: ${source.text_sha256}`)); evidenceSection.append(card);
  }
  const verification = detailSection(container, 'VERIFICATION', 'Review and provenance');
  verification.append(node('p', t.sourceMeaning, 'record-notice'), node('p', record.verification_notes), node('p', `Created: ${dateText(record.record_created_at, true)} · Updated: ${dateText(record.record_updated_at, true)} · Pipeline ${record.pipeline_version}`));
  const historySection = detailSection(container, 'CHANGE HISTORY', 'Record revisions'); const history = node('ol', null, 'history');
  for (const revision of record.history) history.append(node('li', `${dateText(revision.at, true)} · ${revision.status} · ${revision.note}`)); historySection.append(history);
  const disclaimer = detailSection(container, 'DISCLAIMER', 'Interpret with the source and context');
  disclaimer.append(node('p', 'Inclusion is not a finding of wrongdoing. This record is not a safety rating or recommendation. Preserve its source link and context when sharing.', 'notice'));
  const correction = node('a', 'Request a correction for this record', 'button secondary'); correction.href = `corrections.html?event=${encodeURIComponent(record.event_id)}`; disclaimer.append(correction);
  document.title = `${record.event_id} · Source-attributed record · WB Evidence Tracker`;
}
function renderAll() { const stats = aggregate(state.rows); charts(stats); renderFilters(); renderRows(); }

try {
  const [data, status, repository, retired] = await Promise.all([json('data/events.json'), json('status.json'), json('repository.json'), json('data/retired.json')]);
  validateDataset(data); state.rows = data.records; state.retired = retired.records; state.repository = safeExternal(repository.url);
  if (state.repository) document.querySelectorAll('[data-repository]').forEach(anchor => { anchor.href = state.repository; anchor.rel = 'noopener noreferrer'; anchor.target = '_blank'; });
  const stats = aggregate(state.rows);
  for (const [id, key] of [['events', 'total'], ['areas', 'areas_count'], ['establishments', 'establishments_count'], ['sources', 'sources_count']]) $(`metric-${id}`).textContent = stats[key].toLocaleString('en-IN');
  $('coverage-publishers').textContent = stats.publishers_count; $('coverage-records').textContent = stats.total; $('coverage-cross').textContent = stats.coverage.cross_source.count; $('coverage-areas').textContent = stats.areas_count;
  $('menu-availability').textContent = `Available for ${stats.coverage.menu_context.count} of ${stats.total} records`;
  $('last-update').textContent = status.last_successful_update ? dateText(status.last_successful_update, true) : t.notUpdated; $('last-scan').textContent = status.last_source_scan ? dateText(status.last_source_scan, true) : t.notScanned;
  $('dataset-version').textContent = `${data.schema_version} / pipeline ${data.pipeline_version}`; $('run-status').textContent = `Last run result: ${status.last_run_result || 'not reported'}. Published: ${data.record_count}; pending review: ${status.pending_count ?? 'not reported'}.`;
  $('dataset-message').textContent = data.record_count ? `${data.record_count} reviewed public-source records. Every chart selection reveals its contributing evidence.` : t.datasetEmpty;
  renderAll(); detail();
  $('search').addEventListener('input', event => { state.query = event.target.value; renderRows(); });
  $('clear-filter').addEventListener('click', () => { state.filters = {}; state.query = ''; $('search').value = ''; renderAll(); });
} catch {
  $('dataset-message').textContent = t.loadError; $('dataset-message').classList.add('notice');
  $('last-update').textContent = 'Status unavailable'; $('last-scan').textContent = 'Status unavailable'; $('dataset-version').textContent = 'Unavailable'; $('run-status').textContent = 'Could not confirm pipeline status.';
  $('search').disabled = true; $('clear-filter').disabled = true;
}
