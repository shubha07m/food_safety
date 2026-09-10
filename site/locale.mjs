// Static editorial UI translations. Source evidence is never sent to a translation API.
export const language = new URLSearchParams(globalThis.location?.search || '').get('lang') === 'bn' ? 'bn' : 'en';
export const bn = {
  'THE BENGAL': 'দ্য বেঙ্গল', 'FOODPATH': 'ফুডপাথ',
  'THE BENGAL FOODPATH': 'দ্য বেঙ্গল ফুডপাথ',
  'The language model proposes structured candidate records from source documents. Candidates passing all source-grounding, schema, semantic and safety checks may publish automatically; ambiguous cases require human review. The new extractor is initially in shadow evaluation, with model publication disabled. Credentials and strict usage limits are required. Original source evidence remains authoritative. There is no chatbot, model training, VLM or face recognition.': 'ভাষা মডেল উৎসের নথি থেকে তথ্য সাজিয়ে সম্ভাব্য রেকর্ড প্রস্তাব করে। উৎসসমর্থন, তথ্যের কাঠামো, অর্থ ও নিরাপত্তার সমস্ত যাচাই পেরোলে স্বয়ংক্রিয় প্রকাশ সম্ভব; অস্পষ্ট ক্ষেত্রে মানুষের পর্যালোচনা লাগে। নতুন ব্যবস্থা প্রথমে ছায়া-মূল্যায়নে আছে, মডেল থেকে প্রকাশ বন্ধ। অনুমোদিত অ্যাক্সেস ও কঠোর ব্যবহারসীমা প্রয়োজন। মূল উৎসের উদ্ধৃতিই প্রামাণ্য। কোনো চ্যাটবট, মডেল প্রশিক্ষণ, ভিএলএম বা মুখ শনাক্তকরণ নেই।',
  'Independent food-information research for West Bengal': 'পশ্চিমবঙ্গের খাদ্যসংক্রান্ত তথ্য নিয়ে স্বাধীন গবেষণা',
  'Food Safety & Inspection Evidence': 'খাদ্য সুরক্ষা ও পরিদর্শনের উৎসভিত্তিক নথি',
  'Methodology': 'পদ্ধতি', 'Disclaimer': 'দায়-সীমা ও ব্যাখ্যা', 'Corrections': 'সংশোধন',
  'Data': 'তথ্য', 'Privacy': 'গোপনীয়তা', 'Contribute': 'অবদান রাখুন', 'Tracker': 'ট্র্যাকার',
  'Independent public-source research tracker': 'প্রকাশ্য উৎসভিত্তিক স্বাধীন গবেষণা ট্র্যাকার',
  'Not a government database': 'এটি সরকারি তথ্যভান্ডার নয়',
  'Inclusion is not a finding of wrongdoing': 'অন্তর্ভুক্তি কোনো অনিয়মের সিদ্ধান্ত নয়',
  'Skip to content': 'মূল বিষয়বস্তুতে যান', 'PUBLIC BETA': 'পাবলিক বেটা',
  'PUBLIC RECORDS. READ IN CONTEXT.': 'প্রকাশ্য তথ্য। প্রেক্ষাপটসহ পড়ুন।',
  'West Bengal': 'পশ্চিমবঙ্গ', 'Food Safety': 'খাদ্য সুরক্ষা', 'Evidence Tracker.': 'উৎসভিত্তিক তথ্য ট্র্যাকার।',
  'West Bengal Food Safety Evidence Tracker': 'পশ্চিমবঙ্গ খাদ্য সুরক্ষা তথ্য ট্র্যাকার',
  'A clearer view of publicly reported inspections and actions. Trace every number to a record, and every record to its source.': 'প্রকাশ্যে প্রতিবেদিত পরিদর্শন ও পদক্ষেপের তথ্য এক জায়গায়। প্রতিটি সংখ্যার সঙ্গে নথি এবং প্রতিটি নথির সঙ্গে মূল উৎসের যোগসূত্র দেখুন।',
  'Explore the evidence': 'উৎসভিত্তিক নথি দেখুন', 'How this tracker works ↗': 'এই ট্র্যাকার কীভাবে কাজ করে ↗',
  'RESEARCH NOTE / 003': 'গবেষণা-সংক্রান্ত নোট', 'Evidence needs': 'তথ্যের সঙ্গে', 'its context.': 'প্রেক্ষাপটও জরুরি।',
  'An inspection is an event. Inclusion here is not a finding of wrongdoing, a safety rating, or a recommendation about a business.': 'পরিদর্শন একটি ঘটনা। এখানে অন্তর্ভুক্তি অনিয়মের সিদ্ধান্ত, সুরক্ষার মান নির্ধারণ বা কোনো ব্যবসা সম্পর্কে সুপারিশ নয়।',
  'Last successful pipeline update': 'শেষ সফল হালনাগাদ', 'Last successful refresh': 'শেষ সফল হালনাগাদ',
  'Last source scan': 'শেষ উৎস পরীক্ষা', 'Dataset version': 'তথ্যসংগ্রহের সংস্করণ',
  'Source-verifiable events': 'উৎসসমর্থিত ঘটনার নথি', 'Areas represented': 'অন্তর্ভুক্ত এলাকা',
  'Named establishments': 'নাম উল্লেখিত প্রতিষ্ঠান', 'Supporting sources reviewed': 'পরীক্ষিত সমর্থনকারী উৎস',
  'Published records in this tracker': 'এই ট্র্যাকারে প্রকাশিত নথি', 'Distinct reported area names': 'প্রতিবেদনে উল্লেখিত পৃথক এলাকা',
  'Distinct source-stated names': 'উৎসে উল্লেখিত পৃথক নাম', 'Distinct URLs in published records': 'প্রকাশিত নথিতে পৃথক উৎস-লিংক',
  'A browser of reporting, with limits.': 'প্রতিবেদনের তথ্য দেখুন, সীমাবদ্ধতা মনে রাখুন।',
  'Read the full context →': 'সম্পূর্ণ ব্যাখ্যা পড়ুন →',
  'Independent, educational and initially non-commercial. This project organizes public information; it does not express the author’s personal opinion or invite conclusions for or against businesses or groups.': 'স্বাধীন, শিক্ষামূলক এবং প্রাথমিকভাবে অ-বাণিজ্যিক প্রকল্প। এটি প্রকাশ্য তথ্য সাজায়; লেখকের ব্যক্তিগত মত প্রকাশ করে না এবং কোনো ব্যবসা বা গোষ্ঠীর পক্ষে বা বিপক্ষে সিদ্ধান্ত নিতে উৎসাহ দেয় না।',
  '01 / THE PUBLISHED RECORD': '০১ / প্রকাশিত নথি', 'Patterns in the reporting': 'প্রতিবেদনের তথ্যচিত্র',
  'Select a chart item to see': 'চিত্রের কোনো অংশ বেছে নিয়ে দেখুন', 'the evidence behind the count.': 'সংখ্যাটির পেছনের উৎসভিত্তিক নথি।',
  'COVERAGE & LIMITATIONS': 'তথ্যের পরিধি ও সীমাবদ্ধতা', 'How complete is this sample?': 'এই নমুনায় কতটা তথ্য পাওয়া যাচ্ছে?',
  'Coverage measures available fields in this tracker—not the quality or completeness of authority activity.': 'এটি ট্র্যাকারে তথ্য পাওয়ার পরিমাণ বোঝায়—কর্তৃপক্ষের কাজের মান বা পূর্ণতা নয়।',
  'SOURCE COVERAGE': 'উৎসের পরিধি', 'publishers': 'প্রকাশক', 'Published records': 'প্রকাশিত নথি',
  'Cross-source verified': 'স্বাধীন একাধিক উৎসে সমর্থিত',
  'Coverage reflects indexed sources, not publication quality, authority activity, or regional incidence.': 'পরিধি শুধু অন্তর্ভুক্ত উৎস বোঝায়; প্রকাশনার মান, কর্তৃপক্ষের কাজ বা এলাকায় ঘটনার হার নয়।',
  'Reported events over time': 'সময়ের সঙ্গে প্রতিবেদিত ঘটনাগুলি',
  'Source-verifiable records in this tracker—not official inspection totals.': 'এই ট্র্যাকারের উৎসসমর্থিত নথি—সরকারি পরিদর্শনের মোট সংখ্যা নয়।',
  'Geographic view of reported areas': 'প্রতিবেদনে উল্লেখিত এলাকার মানচিত্র',
  'Areas in the records': 'নথিতে উল্লেখিত এলাকা', 'Reported action categories': 'প্রতিবেদিত পদক্ষেপের বিভাগ',
  'Establishment context': 'প্রতিষ্ঠানের প্রেক্ষাপট', 'Records by publisher': 'প্রকাশক অনুযায়ী নথি',
  'Verification status': 'উৎস যাচাইয়ের অবস্থা', 'DERIVED CONTEXT': 'উৎস থেকে নির্ধারিত প্রেক্ষাপট',
  'DATE': 'তারিখ', 'GEOGRAPHY': 'এলাকা', 'ACTION': 'পদক্ষেপ', 'SOURCE MIX': 'উৎসের বিন্যাস',
  'PROVENANCE': 'উৎস-পরিচয়', 'COARSE LOCATION': 'আনুমানিক এলাকা',
  'Contextual classification—not an official food-safety category or finding.': 'প্রেক্ষাপটভিত্তিক শ্রেণিবিভাগ—খাদ্য সুরক্ষা বিষয়ে সরকারি বিভাগ বা সিদ্ধান্ত নয়।',
  'Publisher counts describe source coverage, not credibility rankings.': 'প্রকাশকভিত্তিক সংখ্যা উৎসের পরিধি বোঝায়, বিশ্বাসযোগ্যতার ক্রমতালিকা নয়।',
  'WHAT IS STILL UNKNOWN?': 'কোন তথ্য এখনও অজানা?', 'Missingness is part of the record.': 'অনুপস্থিত তথ্যও স্পষ্টভাবে দেখানো জরুরি।',
  'Menu and business context': 'মেনু ও ব্যবসার প্রেক্ষাপট', 'Only where supported by reliable public evidence': 'শুধু নির্ভরযোগ্য প্রকাশ্য উৎসের সমর্থন থাকলে',
  'CONTEXTUAL CLASSIFICATION — NOT AN OFFICIAL FOOD-SAFETY CATEGORY OR FINDING.': 'প্রেক্ষাপটভিত্তিক শ্রেণিবিভাগ — খাদ্য সুরক্ষা বিষয়ে সরকারি বিভাগ বা সিদ্ধান্ত নয়।',
  'Menu or business context does not indicate safety, guilt, compliance, ownership identity, or social identity.': 'মেনু বা ব্যবসার প্রেক্ষাপট সুরক্ষা, দোষ, বিধি মানা, মালিকের পরিচয় বা সামাজিক পরিচয় নির্দেশ করে না।',
  '02 / FOLLOW THE SOURCE': '০২ / মূল উৎস দেখুন', 'The evidence register': 'উৎসভিত্তিক নথির তালিকা',
  'Data & provenance ↗': 'তথ্য ও উৎস-পরিচয় ↗', 'Search published records': 'প্রকাশিত নথি খুঁজুন',
  'Clear filters': 'সব ফিল্টার সরান', 'Area, establishment, observation…': 'এলাকা, প্রতিষ্ঠান, প্রতিবেদিত তথ্য…',
  'Event date': 'ঘটনার তারিখ', 'Area': 'এলাকা', 'Establishment': 'প্রতিষ্ঠান',
  'Reported observation': 'উৎসে প্রতিবেদিত তথ্য', 'Reported action': 'প্রতিবেদিত পদক্ষেপ',
  'Quantity': 'পরিমাণ', 'Source': 'উৎস', 'Date': 'তারিখ', 'Publisher': 'প্রকাশক', 'Action': 'পদক্ষেপ',
  'Establishment type': 'প্রতিষ্ঠানের ধরন', 'Status': 'অবস্থা', 'Menu': 'মেনু', 'Business format': 'ব্যবসার ধরন',
  'Source-attributed records. Inclusion is not a finding of wrongdoing.': 'উৎসের উল্লেখসহ নথি। অন্তর্ভুক্তি অনিয়মের সিদ্ধান্ত নয়।',
  'No matching published records.': 'এই নির্বাচনের সঙ্গে মেলে এমন প্রকাশিত নথি নেই।',
  'Interpretation and limitations →': 'ব্যাখ্যা ও সীমাবদ্ধতা →',
  'HELP KEEP THE RECORD ACCURATE': 'নথি নির্ভুল রাখতে সাহায্য করুন', 'Corrections are part': 'সংশোধনও', 'of the method.': 'এই পদ্ধতির অংশ।',
  'Request a correction ↗': 'সংশোধনের অনুরোধ করুন ↗', 'Suggest a source': 'একটি উৎসের পরামর্শ দিন',
  'Found a missing context, an updated source, or a field that needs review? Use the documented correction process. No submission publishes automatically.': 'প্রেক্ষাপট বাদ পড়েছে, উৎস বদলেছে বা কোনো তথ্য যাচাই দরকার? নির্ধারিত সংশোধন পদ্ধতি ব্যবহার করুন। জমা দেওয়া কোনো বিষয় নিজে থেকে প্রকাশিত হয় না।',
  'VOLUNTEER MAINTAINERS': 'স্বেচ্ছাসেবী রক্ষণাবেক্ষণকারী', 'Help keep the tracker useful.': 'ট্র্যাকারকে কার্যকর রাখতে সাহায্য করুন।',
  'Volunteer / Contribute': 'স্বেচ্ছাসেবী হিসেবে যোগ দিন / অবদান রাখুন',
  'This independent project welcomes careful volunteers for source review, data validation, Bengali/English coverage and open-data tooling. Contributions must follow the evidence, safety and correction standards.': 'উৎস যাচাই, তথ্য পরীক্ষা, বাংলা ও ইংরেজি প্রতিবেদনের পরিধি বাড়ানো এবং উন্মুক্ত তথ্যপ্রযুক্তির কাজে আগ্রহী স্বেচ্ছাসেবীদের স্বাগত। প্রতিটি অবদানকে উৎস, নিরাপত্তা ও সংশোধনের মানদণ্ড মানতে হবে।',
  'Independent · Educational · Non-governmental': 'স্বাধীন · শিক্ষামূলক · বেসরকারি',
  'Data download': 'তথ্য ডাউনলোড',
  'No rankings. No community inference. No recommendation to patronize or avoid an establishment.': 'কোনো ক্রমতালিকা বা সম্প্রদায়গত অনুমান নয়। কোনো প্রতিষ্ঠানকে বেছে নেওয়া বা এড়ানোর সুপারিশ নয়।',
  'Project policy draft, not legal advice. Independent legal review has not been completed.': 'এটি প্রকল্পের নীতির খসড়া, আইনি পরামর্শ নয়। স্বাধীন আইনি পর্যালোচনা সম্পূর্ণ হয়নি।',
  'Unknown': 'অজানা', 'unknown': 'অজানা', 'Not reported': 'উল্লেখ নেই', 'not reported': 'উল্লেখ নেই',
  'Named establishment': 'নাম উল্লেখিত প্রতিষ্ঠান', 'Reported quantity': 'প্রতিবেদিত পরিমাণ',
  'Menu context': 'মেনুর প্রেক্ষাপট', 'Cross-source verification': 'একাধিক স্বাধীন উৎসে যাচাই',
  'Quantity not reported': 'পরিমাণ উল্লেখ নেই', 'Establishment unnamed': 'প্রতিষ্ঠানের নাম উল্লেখ নেই',
  'Establishment context unknown': 'প্রতিষ্ঠানের প্রেক্ষাপট অজানা', 'Menu context unknown': 'মেনুর প্রেক্ষাপট অজানা',
  'Business format unknown': 'ব্যবসার ধরন অজানা', 'Single-source records': 'একটি উৎসভিত্তিক নথি',
  'records': 'নথি', 'source links': 'উৎস-যোগসূত্র', 'SOURCE VERIFIED': 'উৎসের সমর্থন যাচাই করা হয়েছে',
  'CROSS-SOURCE VERIFIED': 'স্বাধীন একাধিক উৎসে সমর্থন যাচাই করা হয়েছে',
  'inspection / visit only': 'শুধু পরিদর্শন', 'sample collected': 'নমুনা সংগ্রহ',
  'food discarded / destroyed': 'খাবার ফেলে দেওয়া / নষ্ট করা', 'seizure reported': 'জব্দ করার কথা প্রতিবেদিত',
  'notice / advisory issued': 'নোটিশ / নির্দেশিকা জারি', 'lab result reported': 'পরীক্ষাগারের ফল প্রতিবেদিত',
  'multiple actions': 'একাধিক পদক্ষেপ', 'other': 'অন্যান্য', 'sweet shop / bakery': 'মিষ্টির দোকান / বেকারি',
  'independent restaurant / eatery': 'স্বতন্ত্র রেস্তোরাঁ / খাবারের দোকান', 'chain / group': 'চেইন / গোষ্ঠী',
  'mall / food court': 'মল / ফুড কোর্ট', 'market / vendor': 'বাজার / বিক্রেতা', 'hotel / hospitality': 'হোটেল / আতিথেয়তা',
  'veg_only': 'শুধু নিরামিষ', 'non_veg': 'আমিষ', 'mixed': 'মিশ্র', 'independent': 'স্বতন্ত্র', 'chain_group': 'চেইন / গোষ্ঠী',
  'REPORTED FACTS': 'উৎসে প্রতিবেদিত তথ্য', 'SOURCE EVIDENCE': 'মূল উৎসের প্রমাণ-অংশ',
  'VERIFICATION': 'উৎস যাচাই', 'CHANGE HISTORY': 'পরিবর্তনের ইতিহাস', 'DISCLAIMER': 'দায়-সীমা ও ব্যাখ্যা',
  'What the source supports': 'উৎস যে তথ্য সমর্থন করে', 'Reviewed contextual metadata': 'পর্যালোচিত প্রেক্ষাপটের তথ্য',
  'Read the retained source span': 'সংরক্ষিত মূল উৎসের অংশ পড়ুন', 'Review and provenance': 'পর্যালোচনা ও উৎস-পরিচয়',
  'Record revisions': 'নথির সংশোধন', 'Interpret with the source and context': 'মূল উৎস ও প্রেক্ষাপটসহ ব্যাখ্যা করুন',
  'Original source text': 'মূল উৎসের অপরিবর্তিত পাঠ', '← All published records': '← সমস্ত প্রকাশিত নথি',
  'Supporting source ↗': 'সমর্থনকারী উৎস ↗', 'Request a correction for this record': 'এই নথির সংশোধনের অনুরোধ করুন',
  'Kolkata region · enlarged': 'কলকাতা অঞ্চল · বড় করে দেখানো', 'Historical reference boundary · north ↑': 'ঐতিহাসিক সীমানার রূপরেখা · উত্তর ↑',
};
export function tr(value) { return language === 'bn' ? (bn[value] ?? value) : value; }
export function localizedURL(href, lang = language) {
  const url = new URL(href, globalThis.location?.href || 'https://foodsafety.nemoneek.com/');
  if (lang === 'bn') url.searchParams.set('lang', 'bn'); else url.searchParams.delete('lang');
  return url.pathname + url.search + url.hash;
}
export function translateStatic(root = document.body) {
  document.documentElement.lang = language;
  if (language === 'bn') {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const texts = []; while (walker.nextNode()) texts.push(walker.currentNode);
    for (const text of texts) {
      if (text.parentElement.closest('script,style,pre,code,q,blockquote,[data-original]')) continue;
      const value = text.textContent.trim();
      if (bn[value]) text.textContent = text.textContent.replace(value, bn[value]);
    }
    root.querySelectorAll('[aria-label],[placeholder]').forEach(el => {
      for (const attr of ['aria-label', 'placeholder']) if (el.hasAttribute(attr)) el.setAttribute(attr, tr(el.getAttribute(attr)));
    });
  }
  root.querySelectorAll('a[href]').forEach(a => {
    const url = new URL(a.href);
    if (url.origin === location.origin && !/\.(json|csv|svg|png|geojson)$/.test(url.pathname)) a.href = localizedURL(a.href);
  });
  if (!document.querySelector('.language-toggle')) {
    const nav = document.createElement('nav'); nav.className = 'language-toggle'; nav.setAttribute('aria-label', 'Language / ভাষা');
    for (const [lang, label] of [['en', 'EN'], ['bn', 'বাংলা']]) {
      const a = document.createElement('a'); a.href = localizedURL(location.href, lang); a.textContent = label;
      a.lang = lang; a.hreflang = lang; if (lang === language) a.setAttribute('aria-current', 'page'); nav.append(a);
    }
    (document.querySelector('.masthead') || document.querySelector('.policy-nav') || root).append(nav);
  }
}
