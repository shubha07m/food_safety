// Query-based document navigation; no extra runtime dependencies.
export function recordRoute(search) {
  return new URLSearchParams(search).has('event');
}
export function applyRoute(root, search) {
  const detail = recordRoute(search);
  root.getElementById('dashboard-view').hidden = detail;
  root.getElementById('record-detail').hidden = !detail;
  return detail;
}
