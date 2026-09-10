import { language, localizedURL } from './locale.mjs';
import { safeExternal } from './data.mjs';

export const copy = {
  en: {
    heading: 'How record verification works',
    extraction: 'A bounded language model can propose structured records from source documents. Fully source-grounded, policy-safe candidates may publish automatically; ambiguous cases require review. The new extractor is initially in shadow evaluation and does not affect publication. Original evidence remains authoritative. This is not a chatbot.',
    policy: 'New records are published only when a permitted source clearly supports the displayed information. After publication, a source outage or technical page change may produce a dated warning while we retry—not a finding that the report was false. Materially uncertain, corrected or withdrawn evidence leaves active results. Records that cannot be revalidated for 30 days move to an unverifiable archive. Historical status is retained rather than silently deleted.',
    meaning: 'Source verification means the cited source supported the displayed statement at the recorded verification time. It is not an independent finding of fact.',
    lifecycle: 'Publication history', active: 'Active records', ever: 'Ever published', warning: 'Active with source warning', inactive: 'Non-active records', recent: 'First published in the last 7 days',
    counts: 'Active records include records with a source warning. Active and non-active records are subsets of Ever published; do not add overlapping totals. Restoration does not count as a new publication.',
    documents: 'Licensing & Compliance Documents',
    pilot: 'URL-only, manually reviewed pilot. A licence does not establish current food safety; a laboratory result applies only to its stated sample, date and scope. No ratings, awards, uploads or quality endorsements.',
    submit: 'Submit a source or correction', coming: 'Submission form coming shortly',
    submission: 'Submitting a source does not publish it automatically. Private responses are reviewed, then processed through the same source and evidence-validation rules. Do not submit files, personal information or unsupported allegations.',
    warningText: 'Source access warning. Last evidence check:',
    nonActive: 'This record is outside active analytics. Historical status is not a finding that reporting was false.',
    precision: 'Location precision: city, neighborhood and street reference anchors, not establishment addresses. Select a marker to see its evidence.',
    authorship: '© 2026 Shubhabrata Mukherjee · The Bengal FoodPath. Independent public-interest data project. Project code is MIT-licensed where stated. Third-party content and trademarks remain subject to their respective rights.',
  },
  bn: {
    heading: 'নথির উৎস কীভাবে যাচাই করা হয়',
    extraction: 'সীমিত ব্যবহারের একটি ভাষা মডেল উৎসের নথি থেকে তথ্য সাজিয়ে সম্ভাব্য রেকর্ড প্রস্তাব করতে পারে। উৎস, তথ্যের সম্পর্ক ও নিরাপত্তার সমস্ত যাচাই পেরোলে রেকর্ড স্বয়ংক্রিয়ভাবে প্রকাশযোগ্য; অস্পষ্ট ক্ষেত্রে মানুষের পর্যালোচনা লাগে। নতুন ব্যবস্থাটি প্রথমে ছায়া-মূল্যায়নে চলছে, তাই এর ফল প্রকাশিত তথ্যে প্রভাব ফেলে না। মূল উৎসের উদ্ধৃতিই প্রামাণ্য। এটি চ্যাটবট নয়।',
    policy: 'অনুমোদিত উৎস প্রদর্শিত তথ্যকে স্পষ্টভাবে সমর্থন করলেই নতুন নথি প্রকাশিত হয়। প্রকাশের পরে উৎসে প্রবেশের সমস্যা বা ওয়েবপেজের প্রযুক্তিগত পরিবর্তন হলে তারিখসহ সতর্কতা দেখিয়ে আবার পরীক্ষা করা হয়—প্রতিবেদন মিথ্যা বলা হয় না। তথ্যের অর্থ নিয়ে গুরুত্বপূর্ণ অনিশ্চয়তা, সংশোধন বা প্রত্যাহার থাকলে নথি সক্রিয় ফলাফল থেকে সরানো হয়। ৩০ দিন ধরে পুনরায় যাচাই করা না গেলে নথি যাচাই-অসম্ভব সংরক্ষণে যায়। নথি নিঃশব্দে মুছে না দিয়ে তার অবস্থার ইতিহাস রাখা হয়।',
    meaning: 'উৎস যাচাই মানে নির্দিষ্ট যাচাইয়ের সময় উৎসটি প্রদর্শিত বক্তব্য সমর্থন করেছিল। বাস্তব ঘটনা স্বাধীনভাবে প্রমাণ করা হয়েছে—এমন নয়।',
    lifecycle: 'প্রকাশের ইতিহাস', active: 'সক্রিয় নথি', ever: 'এখনও পর্যন্ত প্রকাশিত', warning: 'উৎস-সতর্কতাসহ সক্রিয়', inactive: 'সক্রিয় ফলাফলের বাইরে', recent: 'গত ৭ দিনে প্রথম প্রকাশিত',
    counts: 'উৎস-সতর্কতাযুক্ত নথিও সক্রিয় সংখ্যার অন্তর্ভুক্ত। সক্রিয় ও অ-সক্রিয় নথি এখনও পর্যন্ত প্রকাশিত মোট নথির অংশ; একই নথি দুবার যোগ করবেন না। পুনরায় সক্রিয় হওয়া নতুন প্রকাশ নয়।',
    documents: 'লাইসেন্স ও বিধিপালন-সংক্রান্ত নথি',
    pilot: 'শুধু প্রকাশ্য URL এবং মানুষের পর্যালোচনাভিত্তিক পরীক্ষামূলক বিভাগ। লাইসেন্স বর্তমান খাদ্য সুরক্ষার প্রমাণ নয়; পরীক্ষাগারের ফল কেবল উল্লিখিত নমুনা, তারিখ ও পরিধির জন্য প্রযোজ্য। রেটিং, পুরস্কার, ফাইল আপলোড বা গুণমানের অনুমোদন দেওয়া হয় না।',
    submit: 'উৎস বা সংশোধনের অনুরোধ জমা দিন', coming: 'জমা দেওয়ার ফর্ম শীঘ্রই আসছে',
    submission: 'উৎস জমা দিলেই তা প্রকাশিত হয় না। ব্যক্তিগতভাবে রাখা উত্তর পর্যালোচনার পরে একই উৎস ও প্রমাণ যাচাইয়ের নিয়মে প্রক্রিয়াকরণ হয়। ফাইল, ব্যক্তিগত তথ্য বা অসমর্থিত অভিযোগ দেবেন না।',
    warningText: 'উৎসে প্রবেশের সতর্কতা। শেষ তথ্য যাচাই:',
    nonActive: 'এই নথি সক্রিয় পরিসংখ্যানের বাইরে। এই ঐতিহাসিক অবস্থা প্রতিবেদন মিথ্যা হওয়ার সিদ্ধান্ত নয়।',
    precision: 'অবস্থানের নির্ভুলতা: শহর, পাড়া ও রাস্তার আনুমানিক কেন্দ্র—প্রতিষ্ঠানের ঠিকানা নয়। উৎসভিত্তিক নথি দেখতে চিহ্ন নির্বাচন করুন।',
    authorship: '© ২০২৬ শুভব্রত মুখার্জী · The Bengal FoodPath। স্বাধীন জনস্বার্থমূলক তথ্য প্রকল্প। যেখানে উল্লেখ আছে, প্রকল্পের কোড MIT লাইসেন্সের আওতায়। তৃতীয় পক্ষের বিষয়বস্তু ও ট্রেডমার্কের অধিকার সংশ্লিষ্ট পক্ষের।',
  },
};
const t = copy[language];
export function sourceWarning(record) {
  return record.publication_status === 'active_with_warning'
    ? `${t.warningText} ${record.last_successful_evidence_check_at || '—'}` : '';
}
function element(tag, text) { const el = document.createElement(tag); el.textContent = text; return el; }

export async function phase1() {
  const main = document.querySelector('main');
  if (!main || document.getElementById('phase1-help')) return;
  const footer = document.querySelector('footer') || document.body.appendChild(document.createElement('footer'));
  footer.append(element('p', t.authorship));
  if (new URLSearchParams(location.search).has('event')) return;
  const hero = document.querySelector('.hero .eyebrow');
  if (hero) hero.textContent = language === 'bn' ? 'খাদ্য সুরক্ষা ও পরিদর্শনের উৎসভিত্তিক নথি' : 'FOOD SAFETY & INSPECTION EVIDENCE';
  const oldAccess = document.querySelector('.policy .notice:last-of-type');
  if (oldAccess?.textContent.includes('publicly accessible intake channel')) oldAccess.textContent = t.submission;
  const help = document.createElement('section'); help.id = 'phase1-help'; help.className = 'phase1-panel';
  const details = document.createElement('details');
  details.append(element('summary', t.heading), element('p', t.policy), element('p', t.meaning), element('p', t.extraction));
  const method = element('a', language === 'bn' ? 'সম্পূর্ণ পদ্ধতি →' : 'Read the full methodology →');
  method.href = localizedURL(new URL('methodology.html', import.meta.url).href); details.append(method);
  const pilot = document.createElement('details'); pilot.id = 'compliance-pilot';
  pilot.append(element('summary', t.documents), element('p', t.pilot));
  help.append(details, pilot); (document.getElementById('dashboard-view') || main).append(help);
  try {
    const data = await (await fetch(new URL('data/compliance.json', import.meta.url), { credentials: 'omit' })).json();
    if (!Array.isArray(data.records) || data.record_count !== data.records.length) throw new Error('Invalid document count');
    pilot.append(element('p', `${language === 'bn' ? 'প্রকাশিত নথি' : 'Published documents'}: ${data.records.length}`));
    for (const record of data.records) {
      const url = safeExternal(record.source?.source_url);
      if (!url || record.publication_status !== 'active') continue;
      const link = element('a', record.establishment_name); link.href = url; link.rel = 'noopener noreferrer'; link.target = '_blank';
      const entry = document.createElement('p'); entry.append(link, element('span', ` · ${record.document_date} · ${record.scope}`)); pilot.append(entry);
      const original = element('blockquote', record.source.evidence_quote); original.dataset.original = ''; pilot.append(original);
    }
  } catch { /* No invented document total if data is unavailable. */ }
  const submission = document.createElement('div'); submission.className = 'submission-panel';
  submission.append(element('h3', t.submit), element('p', t.submission)); help.append(submission);
  try {
    const metadata = await (await fetch(new URL('repository.json', import.meta.url), { credentials: 'omit' })).json();
    const url = safeExternal(metadata.community_submission_url);
    const parsed = url && new URL(url);
    const valid = parsed && parsed.protocol === 'https:' && (parsed.hostname === 'forms.gle' || (parsed.hostname === 'docs.google.com' && parsed.pathname.startsWith('/forms/d/e/') && parsed.pathname.endsWith('/viewform')));
    const link = valid ? element('a', t.submit) : element('p', t.coming);
    if (valid) { link.href = url; link.rel = 'noopener noreferrer'; link.target = '_blank'; link.className = 'button primary'; }
    submission.append(link);
    for (const id of ['correction-link', 'source-link']) {
      const old = document.getElementById(id);
      if (old) { old.removeAttribute('target'); old.href = '#phase1-help'; old.textContent = valid ? t.submit : t.coming; }
    }
    const access = document.getElementById('repository-status');
    if (access) access.textContent = t.submission;
  } catch { submission.append(element('p', t.coming)); }
  if (!document.getElementById('metric-events')) return;
  document.querySelector('#metric-events + .metric-label').textContent = t.active;
  const map = document.getElementById('map-coverage'); if (map) map.after(element('p', t.precision));
  try {
    const data = await (await fetch(new URL('data/lifecycle.json', import.meta.url), { credentials: 'omit' })).json();
    const panel = document.createElement('section'); panel.className = 'phase1-panel'; panel.id = 'lifecycle-summary';
    panel.append(element('h2', t.lifecycle));
    const dl = document.createElement('dl'); dl.className = 'lifecycle-metrics';
    for (const [label, number] of [[t.ever, data.ever_published], [t.warning, data.states.active_with_warning || 0], [t.inactive, data.non_active], [t.recent, data.new_last_7_days]]) {
      const block = document.createElement('div'); block.append(element('dt', label), element('dd', number)); dl.append(block);
    }
    panel.append(dl, element('p', t.counts));
    for (const key of ['needs_review', 'archived_unverifiable', 'suspended', 'superseded']) {
      if (data.states[key]) panel.append(element('p', `${key}: ${data.states[key]}`));
    }
    document.querySelector('.metrics').after(panel);
  } catch { /* Never invent counts when an optional summary is unavailable. */ }
}
