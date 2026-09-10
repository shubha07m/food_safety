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

export const recordDate = row => row.reported_fact.event_date
  || row.sources.find(source => source.source_date)?.source_date || 'Unknown';

export const dimensions = {
  timeline: row => recordDate(row),
  areas: row => row.derived_context.normalized_area || row.reported_fact.area || 'Unknown',
  actions: row => row.derived_context.action_category,
  establishments: row => row.derived_context.establishment_context,
  publishers: row => [...new Set(row.sources.map(source => source.source_publisher))],
  verification: row => row.verification_status,
  menus: row => row.derived_context.menu_context,
  business_formats: row => row.derived_context.business_format,
};

const valuesFor = (row, dimension) => {
  const value = dimensions[dimension](row);
  return Array.isArray(value) ? value : [value];
};

export function completeness(rows) {
  const total = rows.length;
  const metric = test => {
    const count = rows.filter(test).length;
    return { count, total, percentage: total ? Math.round((count / total) * 1000) / 10 : 0 };
  };
  return {
    named_establishment: metric(row => Boolean(row.reported_fact.establishment_name)),
    reported_action: metric(row => Boolean(row.reported_fact.reported_action)),
    reported_quantity: metric(row => Boolean(row.reported_fact.reported_quantity)),
    establishment_context: metric(row => row.derived_context.establishment_context !== 'unknown'),
    menu_context: metric(row => row.derived_context.menu_context !== 'unknown'),
    business_format: metric(row => row.derived_context.business_format !== 'unknown'),
    cross_source: metric(row => row.verification_status === 'CROSS-SOURCE VERIFIED'),
  };
}

export function aggregate(rows) {
  const result = {
    total: rows.length,
    areas_count: new Set(rows.map(row => dimensions.areas(row)).filter(value => value !== 'Unknown')).size,
    establishments_count: new Set(rows.map(row => row.reported_fact.establishment_name).filter(Boolean)).size,
    sources_count: new Set(rows.flatMap(row => row.sources.map(source => source.source_url))).size,
    publishers_count: new Set(rows.flatMap(row => dimensions.publishers(row))).size,
    coverage: completeness(rows),
  };
  for (const dimension of Object.keys(dimensions)) {
    const counts = new Map();
    for (const row of rows) {
      for (const value of valuesFor(row, dimension)) counts.set(value, (counts.get(value) || 0) + 1);
    }
    result[dimension] = Object.fromEntries([...counts].sort(([a], [b]) => a.localeCompare(b)));
  }
  return result;
}

export function filterRows(rows, filters = {}, query = '') {
  if (typeof filters === 'string') {
    const dimension = filters;
    const value = arguments[2];
    query = arguments[3] || '';
    filters = value == null ? {} : { [dimension]: value };
  }
  const term = query.trim().toLocaleLowerCase();
  return rows.filter(row => Object.entries(filters).every(([dimension, value]) => (
    !value || valuesFor(row, dimension).includes(value)
  )) && (!term || [
    ...Object.values(row.reported_fact).filter(value => typeof value === 'string'),
    row.display_summary,
    ...row.sources.map(source => source.source_publisher),
  ].filter(Boolean).join(' ').toLocaleLowerCase().includes(term)));
}

export function filterOptions(rows) {
  const stats = aggregate(rows);
  return Object.fromEntries(Object.keys(dimensions).map(dimension => [
    dimension,
    Object.keys(stats[dimension]).filter(value => value !== 'unknown' && value !== 'Unknown'),
  ]));
}

export function validateDataset(data) {
  if (!['1.1.0', '1.2.0'].includes(data.schema_version) || !Array.isArray(data.records) || data.record_count !== data.records.length || !data.context_notice) throw new Error('Invalid dataset');
  const ids = new Set();
  for (const row of data.records) {
    if (row.is_fixture || !/^WBFS-[a-f0-9]{12}$/.test(row.event_id) || ids.has(row.event_id)) throw new Error('Invalid public record');
    ids.add(row.event_id);
    const humanReviewed = row.review?.all_fields_supported && row.review?.source_context_checked;
    const automaticallyValidated = ['explicit_inspection_sentence_v1', 'explicit_inspection_sentence_v2', 'source_grounded_candidate_v1'].includes(row.automatic_validation?.method) && row.automatic_validation?.validated_at;
    if (row.automatic_validation?.method === 'source_grounded_candidate_v1' && (!row.llm?.llm_used || !row.llm.llm_output_was_validated || row.llm.validation_result !== 'passed' || !row.automatic_validation.extraction_evidence || row.llm.source_revision_id !== row.automatic_validation.extraction_evidence.source_revision_id)) throw new Error('Missing model grounding provenance');
    if (!row.context_notice || !row.display_summary || !row.reported_fact || !row.derived_context || !row.sources?.length || !(humanReviewed || automaticallyValidated)) throw new Error('Missing provenance');
    if (!['SOURCE VERIFIED', 'CROSS-SOURCE VERIFIED'].includes(row.verification_status)) throw new Error('Non-public status');
    if (data.schema_version === '1.2.0' && row.publication_status && !['active', 'active_with_warning'].includes(row.publication_status)) throw new Error('Non-active record');
    if (row.sources.some(source => !safeExternal(source.source_url))) throw new Error('Invalid source');
  }
  return data;
}
