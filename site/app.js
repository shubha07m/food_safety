import { aggregate, dimensions, filterRows, safeExternal, validateDataset } from './data.mjs';
import { strings as t } from './strings.mjs';

const $ = id => document.getElementById(id);
const state = { rows: [], dimension: null, value: null, query: '', repository: null, retired: [] };
function node(tag, text, className) {
  const element = document.createElement(tag);
  if (text != null) element.textContent = text;
  if (className) element.className = className;
  return element;
}
function external(label, value) {
  const url = safeExternal(value);
  if (!url) return node('span', 'Source link unavailable');
  const anchor = node('a', label);
  anchor.href = url;
  anchor.target = '_blank';
  anchor.rel = 'noopener noreferrer';
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
function charts(stats) {
  document.querySelectorAll('.chart-notice').forEach(el => { el.textContent = t.chartNotice; });
  for (const dimension of Object.keys(dimensions)) {
    const container = $(`chart-${dimension}`);
    container.replaceChildren();
    const entries = Object.entries(stats[dimension]);
    if (!entries.length) {
      const empty = node('div', null, 'empty-chart');
      empty.append(node('span', '—', 'empty-dash'), node('p', t.chartEmpty), node('small', 'Every count will link to its evidence.'));
      container.append(empty);
      continue;
    }
    const max = Math.max(...entries.map(([, count]) => count));
    for (const [label, count] of entries) {
      const button = node('button', null, 'chart-row');
      button.type = 'button';
      button.setAttribute('aria-pressed', String(state.dimension === dimension && state.value === label));
      button.setAttribute('aria-label', `${label}: ${count} records. Show underlying evidence.`);
      const progress = node('progress');
      progress.max = max; progress.value = count;
      progress.setAttribute('aria-hidden', 'true');
      button.append(node('span', label), progress, node('strong', count));
      button.addEventListener('click', () => {
        state.dimension = dimension; state.value = label;
        charts(stats); renderRows();
        $('evidence').scrollIntoView({ behavior: 'auto', block: 'start' });
        $('clear-filter').focus({ preventScroll: true });
      });
      container.append(button);
    }
  }
}
function renderRows() {
  const rows = filterRows(state.rows, state.dimension, state.value, state.query);
  $('evidence-rows').replaceChildren();
  $('row-count').textContent = `${rows.length} of ${state.rows.length} published records`;
  $('filter-explanation').textContent = state.dimension
    ? `Why am I seeing this number? “${state.value}” has ${aggregate(state.rows)[state.dimension][state.value]} published records. ${state.query ? 'Your search further narrows these rows.' : 'The corresponding source-linked rows appear below.'}`
    : `Why am I seeing this number? ${state.query ? 'Your search matches these published rows.' : 'These are all underlying published records.'}`;
  $('empty-evidence').hidden = rows.length > 0;
  if (!rows.length) {
    $('empty-evidence').querySelector('h3').textContent = state.rows.length ? t.noMatches : 'No published evidence records yet.';
  }
  for (const record of rows) {
    const facts = record.reported_fact;
    const tr = node('tr');
    const name = node('td');
    const link = node('a', facts.establishment_name || 'Establishment unnamed', 'record-link');
    link.href = `?event=${encodeURIComponent(record.event_id)}`;
    name.append(link, node('small', record.event_id));
    const recordDate = facts.event_date || record.sources.find(item => item.source_date)?.source_date;
    for (const text of [dateText(recordDate), facts.area || t.unknown]) tr.append(node('td', text));
    tr.append(name, node('td', `Source states: ${facts.reported_observation}`), node('td', facts.reported_action || t.notReported), node('td', facts.reported_quantity || t.notReported));
    const status = node('td'); status.append(node('span', record.verification_status, 'badge'));
    const source = node('td');
    for (const item of record.sources) source.append(external(`${item.source_publisher} ↗`, item.source_url));
    tr.append(status, source);
    $('evidence-rows').append(tr);
  }
}
function detail() {
  const id = new URLSearchParams(location.search).get('event');
  if (!id) return;
  const container = $('record-detail');
  container.hidden = false;
  const back = node('a', '← All published records', 'text-link'); back.href = 'index.html';
  const title = node('h2', 'Record detail'); title.id = 'record-title';
  container.append(back, title, node('p', t.context, 'notice'));
  const record = state.rows.find(row => row.event_id === id);
  if (!record) {
    const retired = state.retired.find(row => row.event_id === id);
    container.append(node('p', retired ? `${retired.event_id} · ${retired.verification_status}. This record is suspended from public evidence and statistics. Updated ${dateText(retired.record_updated_at, true)}.` : 'No published record is available at this address.'));
    const correction = node('a', 'Correction and dispute process'); correction.href = 'corrections.html';
    container.append(correction); return;
  }
  title.textContent = record.reported_fact.establishment_name || 'Establishment unnamed';
  document.title = `${record.event_id} · Source-attributed record · WB Evidence Tracker`;
  container.append(node('p', `${record.event_id} · ${record.verification_status}`, 'eyebrow'), node('p', t.sourceMeaning, 'record-notice'));
  const fields = node('dl', null, 'detail-fields');
  const labels = { event_date: 'Event date', area: 'Reported area', district: 'Reported district', establishment_name: 'Establishment', establishment_type: 'Reported establishment type', reported_observation: 'Source-reported observation', reported_action: 'Reported action', reported_quantity: 'Reported quantity', reported_authority: 'Reported authority', legal_finding_status: 'Formal legal finding status', formal_finding: 'Source-reported formal finding' };
  for (const [key, label] of Object.entries(labels)) {
    fields.append(node('dt', label), node('dd', record.reported_fact[key] || t.notReported));
    const support = record.reported_fact.evidence[key];
    if (support) {
      const evidence = node('dd', null, 'field-evidence');
      evidence.append(node('q', support.quote), document.createTextNode(' '), external('Supporting source ↗', support.source_url));
      fields.append(evidence);
    }
  }
  container.append(fields, node('h3', 'Sources & evidence'));
  for (const source of record.sources) {
    const card = node('article', null, 'source-card');
    card.append(external(source.source_title, source.source_url), node('p', `${source.source_publisher} · Tier ${source.tier} · Publication date: ${dateText(source.source_date)} · Retrieved: ${dateText(source.retrieved_at, true)}`), node('blockquote', source.evidence_quote), node('p', `Evidence context: ${source.evidence_context}`), node('small', `Extracted-text SHA-256: ${source.text_sha256}`));
    if (source.archive_url) card.append(external('Available archive ↗', source.archive_url));
    container.append(card);
  }
  container.append(node('h3', 'Derived context'), node('p', t.contextCategory, 'notice'));
  const context = record.derived_context;
  container.append(node('p', `Menu: ${context.derived_menu_category} · Business format: ${context.derived_owner_category} · Action grouping: ${context.action_category} · Geography: ${context.derived_geography || t.unknown}`), node('p', `${context.derived_context_method} Confidence: ${context.derived_confidence}.`));
  for (const url of context.derived_context_sources) container.append(external('Context source ↗', url));
  container.append(node('h3', 'Review, provenance & history'), node('p', record.verification_notes), node('p', `Created: ${dateText(record.record_created_at, true)} · Updated: ${dateText(record.record_updated_at, true)} · Pipeline ${record.pipeline_version}`));
  if (record.review) container.append(node('p', `Context reviewed by ${record.review.reviewer} at ${dateText(record.review.reviewed_at, true)}. ${record.review.note}`));
  const llm = record.llm;
  container.append(node('p', llm.llm_used ? `LLM assistance: ${llm.llm_provider} / ${llm.llm_model}; task: ${llm.llm_task}; pipeline ${llm.llm_pipeline_version}; output validated: ${llm.llm_output_was_validated ? 'yes' : 'no'}. Model output is not evidence.` : 'LLM assistance: not used.'));
  const history = node('ol', null, 'history');
  for (const revision of record.history) history.append(node('li', `${dateText(revision.at, true)} · ${revision.status} · ${revision.note}`));
  container.append(history, node('p', `Correction/dispute status: ${record.verification_status}. Records may be suspended when context or accuracy is uncertain.`));
  const correction = node('a', 'Request a correction for this record', 'button secondary');
  correction.href = `corrections.html?event=${encodeURIComponent(record.event_id)}`;
  container.append(correction, node('p', 'Share this stable URL with its source links and disclaimer. Third-party interpretation does not represent the project.', 'fine-print'));
}

try {
  const [data, status, repository, retired] = await Promise.all([
    json('data/events.json'), json('status.json'), json('repository.json'), json('data/retired.json'),
  ]);
  validateDataset(data);
  state.rows = data.records; state.retired = retired.records;
  state.repository = safeExternal(repository.url);
  if (state.repository) document.querySelectorAll('[data-repository]').forEach(a => {
    a.href = state.repository; a.rel = 'noopener noreferrer'; a.target = '_blank';
  });
  const stats = aggregate(state.rows);
  for (const [id, key] of [['events', 'total'], ['areas', 'areas_count'], ['establishments', 'establishments_count'], ['sources', 'sources_count']]) $(`metric-${id}`).textContent = stats[key].toLocaleString('en-IN');
  $('last-update').textContent = status.last_successful_update ? dateText(status.last_successful_update, true) : t.notUpdated;
  $('last-scan').textContent = status.last_source_scan ? dateText(status.last_source_scan, true) : t.notScanned;
  $('dataset-version').textContent = `${data.schema_version} / pipeline ${data.pipeline_version}`;
  $('run-status').textContent = `Last run: ${status.last_run_result.replaceAll('_', ' ')}. ${status.pending_count} pending review. Scheduled publication is not enabled.`;
  $('dataset-message').textContent = state.rows.length ? `${state.rows.length} source-attributed records. Counts reflect this dataset's coverage only.` : t.noRecords;
  charts(stats); renderRows(); detail();
  $('search').addEventListener('input', event => { state.query = event.target.value; renderRows(); });
  $('clear-filter').addEventListener('click', () => {
    state.dimension = null; state.value = null; state.query = ''; $('search').value = '';
    charts(stats); renderRows();
  });
} catch {
  $('dataset-message').textContent = t.loadError;
  $('dataset-message').classList.add('notice');
  $('last-update').textContent = 'Status unavailable';
  $('last-scan').textContent = 'Status unavailable';
  $('dataset-version').textContent = 'Unavailable';
  $('run-status').textContent = 'Could not confirm pipeline status.';
  $('search').disabled = true; $('clear-filter').disabled = true;
}
