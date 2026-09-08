import { safeExternal } from './data.mjs';
import { translateStatic, language } from './locale.mjs';

translateStatic();
if (language === 'bn' && document.querySelector('main')) {
  const note = document.createElement('aside'); note.className = 'notice';
  note.textContent = 'স্বাধীন, শিক্ষামূলক, প্রকাশ্য উৎসভিত্তিক গবেষণা—সরকারি তথ্যভান্ডার নয়। অন্তর্ভুক্তি অনিয়মের সিদ্ধান্ত নয়। উৎস যাচাই মানে উৎসটি বক্তব্য সমর্থন করে; বাস্তব সত্য স্বাধীনভাবে প্রমাণ করা নয়। সংখ্যা সমস্ত পরিদর্শনের মোট হিসাব নয়। কোনো ধর্ম, জাতি, বর্ণ, সম্প্রদায় বা রাজনৈতিক পরিচয় অনুমান করা হয় না। প্রেক্ষাপটভিত্তিক বিভাগ সরকারি সিদ্ধান্ত নয়। মূল উৎস ও উদ্ধৃতি অপরিবর্তিত থাকে। নীতির পূর্ণ ইংরেজি পাঠও উপলব্ধ; বাংলা সারসংক্ষেপ আইনি পরামর্শ নয়।';
  document.querySelector('main').prepend(note);
}

try {
  const response = await fetch(new URL('repository.json', import.meta.url), { credentials: 'omit' });
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
