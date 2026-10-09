// One local recording, loaded only after an explicit gesture. No saved preference.
export function initDhaak({ doc = document, win = window } = {}) {
  const button = doc.getElementById('dhaak-toggle'); const audio = doc.getElementById('dhaak-audio');
  const label = doc.getElementById('dhaak-label'); const message = doc.getElementById('dhaak-status');
  if (!button || !audio || !label || !message) return;
  const bn = doc.documentElement.lang === 'bn';
  let enabled = false; let revision = 0;
  const appropriate = () => doc.body.classList.contains('puja-route') && doc.visibilityState !== 'hidden'
    && doc.getElementById('regional-food-discovery')?.hidden !== false;
  const paint = () => {
    button.setAttribute('aria-pressed', String(enabled));
    label.textContent = enabled ? (bn ? 'ঢাক থামান' : 'Stop dhaak') : (bn ? 'ঢাক শুনুন' : 'Hear the dhaak');
  };
  const stop = () => {
    enabled = false; revision++; audio.pause(); audio.loop = false;
    try { audio.currentTime = 0; } catch { /* Not loaded yet. */ }
    paint();
  };
  const failed = () => { stop(); message.textContent = bn ? 'এই মুহূর্তে ঢাক বাজানো যাচ্ছে না।' : 'Dhaak playback is unavailable right now.'; };
  paint(); audio.preload = 'none'; audio.volume = 0.22;
  button.addEventListener('click', async () => {
    if (enabled) { stop(); return; }
    if (!appropriate()) return;
    message.textContent = ''; enabled = true; const run = ++revision; paint();
    if (!audio.getAttribute('src')) audio.setAttribute('src', 'assets/puja/dhaak.mp3');
    audio.loop = true;
    try { await audio.play(); if (run === revision && !appropriate()) stop(); }
    catch { if (run === revision) failed(); }
  });
  audio.addEventListener('ended', stop);
  audio.addEventListener('pause', () => { if (enabled && audio.paused) stop(); });
  audio.addEventListener('error', failed);
  doc.addEventListener('visibilitychange', () => { if (!appropriate()) stop(); });
  win.addEventListener('pagehide', stop);
  win.addEventListener('popstate', () => { if (!appropriate() || new URLSearchParams(win.location.search).has('event') || new URLSearchParams(win.location.search).get('module') === 'safety') stop(); });
  // Stop before document navigation, including the Food Safety link; region buttons stay local.
  doc.addEventListener('click', e => { if (e.target.closest?.('a[href], #food-view-bengali') && enabled) stop(); }, true);
  if (win.MutationObserver) new win.MutationObserver(() => { if (!appropriate()) stop(); }).observe(doc.body, { attributes: true, attributeFilter: ['class'] });
  return { stop };
}
