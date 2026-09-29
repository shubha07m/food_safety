// Mirrors puja/location.py; shared fixtures test the static/operator boundary.
export function effectiveLocation(p, year = new Date().getUTCFullYear()) {
  const e = p.edition || {}; const current = e.year === year && e.confirmed === true;
  const source = e.location ?? p;
  const stale = !!p.edition && e.year !== year;
  const withheld = !!p.edition && !e.location;
  const { latitude: lat, longitude: lon, coordinate_precision: precision } = source;
  const mapped = p.enabled !== false && !stale && !withheld && Number.isFinite(lat) && Math.abs(lat) <= 90
    && Number.isFinite(lon) && Math.abs(lon) <= 180 && !!source.coordinate_source;
  // Address-only directions require this edition's evidenced override, never a legacy address.
  const reviewedAddress = !!e.location && lat == null && lon == null
    && !!source.venue?.trim() && !!source.address?.trim() && !!source.evidence?.length;
  return { venue: source.venue ?? null, address: source.address ?? null, city: source.city ?? null,
    latitude: mapped ? lat : null, longitude: mapped ? lon : null,
    coordinate_source: mapped ? source.coordinate_source : null, coordinate_precision: mapped ? precision : null,
    status: stale ? (e.year < year ? 'historical' : 'other_edition') : current && e.venue_reviewed && e.location ? 'current' : 'last_known',
    map_eligible: mapped, near_me_eligible: mapped && precision === 'venue',
    directions_eligible: p.enabled !== false && current && e.venue_reviewed === true
      && ((mapped && precision === 'venue') || reviewedAddress),
    anchor_key: mapped ? `${lat.toFixed(7)},${lon.toFixed(7)}` : null };
}
export function publicationLabel(p, year = new Date().getUTCFullYear(), bn = false) {
  const e = p.edition;
  if (!e?.confirmed || e.year !== year) return bn ? 'উৎসে তালিকাভুক্ত · বর্তমান স্থান পর্যালোচিত নয়' : 'Source-listed · current venue not reviewed';
  if (e.venue_reviewed && e.location && e.start_date) return bn ? `${e.year} সালের স্থান/তারিখ পর্যালোচিত` : `${e.year} venue/date reviewed`;
  return bn ? `${e.year} সালের আয়োজন নিশ্চিত` : `${e.year} event confirmed`;
}
