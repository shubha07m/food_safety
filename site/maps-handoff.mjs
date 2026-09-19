// Keyless Maps Search contract shared by every region/provider with durable names.
// https://developers.google.com/maps/documentation/urls/get-started
const clean = value => typeof value === 'string' ? value.normalize('NFC').trim().replace(/\s+/g, ' ') : '';
export function foodMapsURL(poi, { locality = [], verifiedPlaceID = null } = {}) {
  if (!Number.isFinite(poi.latitude) || !Number.isFinite(poi.longitude)
    || Math.abs(poi.latitude) > 90 || Math.abs(poi.longitude) > 180) return null;
  const coordinates = `${poi.latitude.toFixed(7)},${poi.longitude.toFixed(7)}`;
  const name = clean(poi.name);
  // Bare coordinates drop the identity. Name+coordinates alone can be interpreted
  // near the browser's location: preserve the independently sourced locality too.
  // Locality is search context, NOT a claimed restaurant street address.
  const context = [...new Set(locality.map(clean).filter(Boolean))];
  const query = name ? [name, ...context, coordinates].join(', ') : coordinates;
  const params = new URLSearchParams({ api: '1', query });
  // Caller must supply a reviewed crosswalk, never a suggested ID from the POI.
  if (verifiedPlaceID !== null) {
    if (typeof verifiedPlaceID !== 'string' || !/^[A-Za-z0-9_-]{1,255}$/.test(verifiedPlaceID)) return null;
    params.set('query_place_id', verifiedPlaceID);
  }
  return `https://www.google.com/maps/search/?${params}`;
}
