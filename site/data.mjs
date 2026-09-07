export function safeExternal(value) {
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase().replace(/\.$/, '');
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password) return null;
    if (host === 'localhost' || !host.includes('.') || host.endsWith('.local') || host.endsWith('.localhost')) return null;
    if (/^(127\.|10\.|192\.168\.|169\.254\.|0\.|172\.(1[6-9]|2\d|3[01])\.)/.test(host)) return null;
    if (url.port && !['80', '443'].includes(url.port)) return null;
    return url.href;
  } catch { return null; }
}

export const dimensions = {
  timeline: row => row.reported_fact.event_date || 'Unknown',
  areas: row => row.reported_fact.area || 'Unknown',
  actions: row => row.derived_context.action_category,
  owners: row => row.derived_context.derived_owner_category,
  menus: row => row.derived_context.derived_menu_category,
};

export function aggregate(rows) {
  const result = {
    total: rows.length,
    areas_count: new Set(rows.map(r => r.reported_fact.area).filter(Boolean)).size,
    establishments_count: new Set(rows.map(r => r.reported_fact.establishment_name).filter(Boolean)).size,
    sources_count: new Set(rows.flatMap(r => r.sources.map(s => s.source_url))).size,
  };
  for (const [dimension, getter] of Object.entries(dimensions)) {
    const counts = new Map();
    for (const row of rows) {
      const key = getter(row);
      counts.set(key, (counts.get(key) || 0) + 1);
    }
    result[dimension] = Object.fromEntries([...counts].sort(([a], [b]) => a.localeCompare(b)));
  }
  return result;
}

export function filterRows(rows, dimension = null, value = null, query = '') {
  const term = query.trim().toLocaleLowerCase();
  return rows.filter(row => (!dimension || dimensions[dimension](row) === value) && (
    !term || Object.values(row.reported_fact).filter(v => typeof v === 'string')
      .join(' ').toLocaleLowerCase().includes(term)
  ));
}

export function validateDataset(data) {
  if (data.schema_version !== '1.0.0' || !Array.isArray(data.records) || data.record_count !== data.records.length || !data.context_notice) throw new Error('Invalid dataset');
  const ids = new Set();
  for (const row of data.records) {
    if (row.is_fixture || !/^WBFS-[a-f0-9]{12}$/.test(row.event_id) || ids.has(row.event_id)) throw new Error('Invalid public record');
    ids.add(row.event_id);
    if (!row.context_notice || !row.reported_fact || !row.derived_context || !row.sources?.length || !row.review?.all_fields_supported || !row.review?.source_context_checked) throw new Error('Missing provenance');
    if (!['SOURCE VERIFIED', 'CROSS-SOURCE VERIFIED'].includes(row.verification_status)) throw new Error('Non-public status');
    if (row.sources.some(s => !safeExternal(s.source_url))) throw new Error('Invalid source');
  }
  return data;
}
