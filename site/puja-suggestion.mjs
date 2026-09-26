export function googleFormURL(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.username || url.password || url.hash) return null;
    if (url.hostname === 'forms.gle' && url.pathname.length > 5) return url.href;
    if (url.hostname === 'docs.google.com'
      && /^\/forms\/d\/e\/[^/]+\/viewform\/?$/.test(url.pathname)) return url.href;
  } catch { /* Unconfigured or malformed URL stays unavailable. */ }
  return null;
}

export function showPujaSuggestion(container, value) {
  const url = googleFormURL(value);
  if (!container || !url) return false;
  const link = container.ownerDocument.createElement('a');
  link.className = 'text-link';
  link.textContent = 'Suggest a Puja ↗';
  link.href = url;
  link.target = '_blank';
  link.rel = 'noopener noreferrer';
  container.replaceChildren(link);
  return true;
}
