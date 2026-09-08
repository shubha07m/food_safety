// Centralized dynamic UI copy; a Bengali dictionary can implement the same keys.
import { language } from './locale.mjs';
const en = {
  unknown: 'Unknown',
  notReported: 'Not reported',
  noRecords: 'No published records yet. Awaiting source and context review.',
  chartEmpty: 'No published records to summarize.',
  chartNotice: 'Counts describe source-verifiable records in this tracker, not all inspections conducted by authorities. They must not be interpreted as prevalence, compliance, risk, wrongdoing, or group-level behavior.',
  sourceMeaning: 'SOURCE VERIFIED means the cited source exists and supports the displayed statement. It does not mean the project independently established the underlying real-world event as true.',
  context: 'Independent, non-governmental public-source research. Inclusion is not a finding of wrongdoing. Inspect the original sources and preserve this context when sharing.',
  contextCategory: 'Contextual classification, not an official food-safety category or finding.',
  notScanned: 'Not yet scanned',
  notUpdated: 'No successful source update yet',
  loadError: 'The dataset could not be loaded or validated. No statistics are displayed. Please try again later.',
  noMatches: 'No records match these filters.',
};
const bn = {
  unknown: 'অজানা', notReported: 'উল্লেখ নেই',
  noRecords: 'এখনও কোনো নথি প্রকাশিত হয়নি।', chartEmpty: 'সারসংক্ষেপ দেখানোর মতো প্রকাশিত নথি নেই।',
  chartNotice: 'সংখ্যাগুলি এই ট্র্যাকারের উৎসসমর্থিত নথি বোঝায়, কর্তৃপক্ষের সমস্ত পরিদর্শন নয়। এগুলি ঘটনার ব্যাপকতা, বিধি মানা, ঝুঁকি, অনিয়ম বা কোনো গোষ্ঠীর আচরণের পরিমাপ নয়।',
  sourceMeaning: 'উৎস যাচাই করার অর্থ, উদ্ধৃত উৎসটি রয়েছে এবং প্রদর্শিত বক্তব্যকে সমর্থন করে। এর অর্থ প্রকল্পটি বাস্তব ঘটনাটিকে স্বাধীনভাবে সত্য বলে প্রতিষ্ঠা করেছে, এমন নয়।',
  context: 'স্বাধীন, বেসরকারি, প্রকাশ্য উৎসভিত্তিক গবেষণা। অন্তর্ভুক্তি অনিয়মের সিদ্ধান্ত নয়। মূল উৎস পড়ুন এবং শেয়ার করার সময় এই প্রেক্ষাপট বজায় রাখুন।',
  contextCategory: 'প্রেক্ষাপটভিত্তিক শ্রেণিবিভাগ; খাদ্য সুরক্ষা বিষয়ে সরকারি বিভাগ বা সিদ্ধান্ত নয়।',
  notScanned: 'এখনও উৎস পরীক্ষা হয়নি', notUpdated: 'এখনও সফল হালনাগাদ হয়নি',
  loadError: 'তথ্য লোড বা যাচাই করা যায়নি। কোনো পরিসংখ্যান দেখানো হচ্ছে না। পরে আবার চেষ্টা করুন।',
  noMatches: 'এই ফিল্টারের সঙ্গে মেলে এমন নথি নেই।',
};
export const strings = language === 'bn' ? bn : en;
