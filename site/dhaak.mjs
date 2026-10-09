// One local recording, loaded only after an explicit gesture. No saved preference.
export function initDhaak({ doc = document, win = window } = {}) {
  const button = doc.getElementById('dhaak-toggle'); const audio = doc.getElementById('dhaak-audio');
  const label = doc.getElementById('dhaak-label'); const message = doc.getElementById('dhaak-status');
  const video = doc.getElementById('dhaak-video');
  const motion = win.matchMedia?.('(prefers-reduced-motion: reduce)');
  if (!button || !audio || !label || !message) return;
  const bn = doc.documentElement.lang === 'bn';
  let enabled = false; let revision = 0;
  const appropriate = () => doc.body.classList.contains('puja-route') && doc.visibilityState !== 'hidden'
    && doc.getElementById('regional-food-discovery')?.hidden !== false;
  const paint = () => {
    button.setAttribute('aria-pressed', String(enabled));
    label.textContent = enabled ? (bn ? 'ঢাক থামান' : 'Stop dhaak') : (bn ? 'ঢাক শুনুন' : 'Hear the dhaak');
  };
  const mute = () => { if (video) { if (!video.muted) video.muted = true; if (!video.defaultMuted) video.defaultMuted = true; if (video.volume !== 0) video.volume = 0; } };
  const stopVisual = () => {
    button.setAttribute('data-animated', 'false');
    if (!video) return;
    video.style.visibility = 'hidden'; video.pause(); video.loop = false;
    try { video.currentTime = 0; } catch { /* Not loaded yet. */ }
  };
  const startVisual = async () => {
    if (!video || motion?.matches || !enabled || audio.paused || !appropriate()) return;
    const run = revision;
    mute(); video.loop = true;
    if (!video.getAttribute('src')) video.setAttribute('src', 'assets/puja/dhaak-playing.mp4');
    try {
      await video.play();
      if (run === revision && enabled && !audio.paused && !motion?.matches && appropriate()) {
        video.style.visibility = 'visible'; button.setAttribute('data-animated', 'true');
      }
      else if (!enabled || motion?.matches || !appropriate()) stopVisual();
    } catch { if (run === revision) stopVisual(); /* Decoration never interrupts sound. */ }
  };
  const stop = () => {
    enabled = false; revision++; audio.pause(); audio.loop = false;
    stopVisual();
    try { audio.currentTime = 0; } catch { /* Not loaded yet. */ }
    paint();
  };
  const failed = () => { stop(); message.textContent = bn ? 'এই মুহূর্তে ঢাক বাজানো যাচ্ছে না।' : 'Dhaak playback is unavailable right now.'; };
  paint(); audio.preload = 'none'; audio.volume = 0.22;
  if (video) { video.preload = 'none'; mute(); stopVisual(); video.addEventListener('volumechange', mute); video.addEventListener('error', stopVisual); }
  motion?.addEventListener('change', () => { if (motion.matches) stopVisual(); else startVisual(); });
  button.addEventListener('click', async () => {
    if (enabled) { stop(); return; }
    if (!appropriate()) return;
    message.textContent = ''; enabled = true; const run = ++revision; paint();
    if (!audio.getAttribute('src')) audio.setAttribute('src', 'assets/puja/dhaak.mp3');
    audio.loop = true;
    try { await audio.play(); if (run === revision) { if (!appropriate()) stop(); else await startVisual(); } }
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
