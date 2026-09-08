// Local reference geometry only. No tiles, geocoder, inferred coordinates or external requests.
export function mappedRows(rows) {
  return rows.filter(({ derived_context: c }) => c.location_reviewed === true
    && ['street', 'neighborhood', 'city', 'establishment'].includes(c.location_precision)
    && Number.isFinite(c.latitude) && Number.isFinite(c.longitude)
    && c.latitude >= 21.4 && c.latitude <= 27.3 && c.longitude >= 85.7 && c.longitude <= 90
    && c.location_source);
}
export function projection(bounds, box) {
  const [west, south, east, north] = bounds;
  const [left, top, width, height] = box;
  const cosine = Math.cos((north + south) / 2 * Math.PI / 180);
  const scale = Math.min(width / ((east - west) * cosine), height / (north - south));
  const dx = (width - (east - west) * cosine * scale) / 2;
  const dy = (height - (north - south) * scale) / 2;
  return ([lon, lat]) => [left + dx + (lon - west) * cosine * scale, top + dy + (north - lat) * scale];
}
export function geometryPath(geometry, project) {
  const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates;
  return polygons.flatMap(polygon => polygon.map(ring => ring.map((point, i) => {
    const [x, y] = project(point);
    return `${i ? 'L' : 'M'}${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(' ') + 'Z')).join(' ');
}
