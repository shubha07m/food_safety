// Query-based document navigation; no extra runtime dependencies.
export function recordRoute(search) {
  return new URLSearchParams(search).has('event');
}
export function safetyRoute(search) {
  return !recordRoute(search) && new URLSearchParams(search).get('module') === 'safety';
}
export function applyRoute(root, search) {
  const detail = recordRoute(search);
  const safety = safetyRoute(search);
  root.getElementById('dashboard-view').hidden = detail;
  root.getElementById('record-detail').hidden = !detail;
  root.body?.classList.toggle('safety-route', safety);
  root.body?.classList.toggle('puja-route', !detail && !safety);
  root.querySelectorAll?.('.puja-only').forEach(node => { node.hidden = detail || safety; });
  root.querySelectorAll?.('.safety-only').forEach(node => { node.hidden = detail || !safety; });
  root.querySelector?.('.evidence-banner')?.toggleAttribute('hidden', !detail && !safety);
  return detail;
}
