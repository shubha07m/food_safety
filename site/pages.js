import { safeExternal } from './data.mjs';

try {
  const response = await fetch('repository.json', { credentials: 'omit' });
  if (!response.ok) throw new Error('Unavailable');
  const repository = (await response.json()).url;
  const safe = safeExternal(repository);
  if (safe && new URL(safe).hostname === 'github.com') {
    const base = safe.replace(/\/$/, '');
    for (const link of document.querySelectorAll('[data-repository]')) {
      link.href = base; link.textContent = 'GitHub ↗';
      link.rel = 'noopener noreferrer'; link.target = '_blank';
    }
    const id = new URLSearchParams(location.search).get('event');
    const correction = document.getElementById('correction-link');
    const source = document.getElementById('source-link');
    if (correction) {
      correction.href = base + '/issues/new?template=correction.yml' + (/^WBFS-[a-f0-9]{12}$/.test(id || '') ? '&record_id=' + encodeURIComponent(id) : '');
      correction.rel = 'noopener noreferrer'; correction.target = '_blank';
    }
    if (source) {
      source.href = base + '/issues/new?template=source_submission.yml';
      source.rel = 'noopener noreferrer'; source.target = '_blank';
    }
  }
} catch { /* The visible local correction instructions remain available. */ }
