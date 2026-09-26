import { safeExternal } from './data.mjs';
import { effectiveLocation, publicationLabel } from './puja-location.mjs';
import { pujaLink, directionsURL, reportURL } from './global-puja.mjs';

function node(doc, tag, value, cls) {
  const n = doc.createElement(tag); if (value != null) n.textContent = value;
  if (cls) n.className = cls; return n;
}
function link(doc, label, url, cls = '') {
  const href = safeExternal(url); if (!href) return null;
  const a = node(doc, 'a', label, cls); a.href = href; a.target = '_blank'; a.rel = 'noopener noreferrer'; return a;
}
export function profileView(p, region, checks = [], year = new Date().getUTCFullYear(), bn = false) {
  const current = p.edition?.year === year;
  const loc = effectiveLocation(p, year);
  const urls = new Set((p.sources || []).map(s => s.source_url));
  const dateText = value => new Intl.DateTimeFormat(bn ? 'bn' : 'en-GB', { day:'numeric',month:'short',year:'numeric',timeZone:'UTC' }).format(new Date(`${value}T12:00:00Z`));
  return { name: bn && p.name_bn ? p.name_bn : p.name, region: [...new Set([region.label,loc.city].filter(Boolean))].join(' · '),
    status: publicationLabel(p, year, bn), location: loc,
    dates: current && p.edition.start_date ? [p.edition.start_date, p.edition.end_date !== p.edition.start_date ? p.edition.end_date : null].filter(Boolean).map(dateText).join(' – ') : null,
    notes: current ? (p.edition.programme_notes || []).slice(0, 3) : [],
    links: (p.official_links || []).filter(l => l.evidence && safeExternal(l.url)),
    checked: checks.filter(c => urls.has(c.url)).map(c => c.last_success).filter(Boolean).sort().at(-1),
    pending: checks.some(c => urls.has(c.url) && c.pending_change),
  };
}
export function renderProfile(p, region, checks, bn = false, doc = document) {
  const v = profileView(p, region, checks, undefined, bn);
  const t = (en, bengali) => bn ? bengali : en;
  const card = node(doc, 'article', null, 'puja-profile'); card.setAttribute('aria-labelledby', 'selected-pandal-title');
  card.append(node(doc, 'p', t('Puja profile', 'পুজোর পরিচিতি'), 'eyebrow'));
  const title = node(doc, 'h3', v.name); title.id = 'selected-pandal-title'; title.tabIndex = -1;
  card.append(title, node(doc, 'p', v.region, 'pandal-area'), node(doc, 'p', v.status, 'profile-status'));
  if (v.dates) card.append(node(doc, 'p', v.dates, 'profile-dates'));
  if (v.location.venue) card.append(node(doc, 'p', v.location.venue, 'profile-venue'));
  if (v.location.address) card.append(node(doc, 'p', v.location.address, 'profile-address'));
  const locationCopy = v.location.status === 'historical' ? t('Historical venue — not used for current proximity or directions.', 'পুরনো স্থান — বর্তমান দূরত্ব বা যাতায়াতের জন্য নয়।')
    : v.location.status === 'other_edition' ? t('Venue belongs to another edition — not used for current proximity.', 'অন্য বছরের আয়োজনের স্থান — বর্তমান দূরত্বের জন্য নয়।')
    : !v.location.map_eligible && v.location.venue && !p.edition?.location ? t('Last-known venue; the current edition location has not been reviewed.', 'সর্বশেষ জানা স্থান; বর্তমান আয়োজনের স্থান পর্যালোচিত নয়।')
    : !v.location.map_eligible ? t('Current map location is not independently reviewed.', 'বর্তমান মানচিত্রের অবস্থান স্বাধীনভাবে পর্যালোচিত নয়।')
      : v.location.status === 'last_known' ? t('Last-known sourced location; this does not confirm the current event venue.', 'উৎসসমর্থিত সর্বশেষ জানা স্থান; বর্তমান আয়োজনের স্থান নিশ্চিত নয়।')
        : v.location.coordinate_precision !== 'venue' ? t('Approximate geographic anchor — not an exact entrance.', 'আনুমানিক অবস্থান — নির্দিষ্ট প্রবেশপথ নয়।') : null;
  if (locationCopy) card.append(node(doc, 'p', locationCopy, 'fine-print'));
  const actions = node(doc, 'div', null, 'puja-actions');
  const direction = directionsURL(p); if (direction) actions.append(link(doc, t('Directions', 'যাতায়াতের পথ'), direction, 'button secondary'));
  const official = v.links.find(l => l.kind === 'website');
  if (official) actions.append(link(doc, t('Official site', 'অফিশিয়াল ওয়েবসাইট'), official.url, 'button secondary'));
  const share = node(doc, 'button', t('Share Puja', 'পুজোর লিঙ্ক শেয়ার করুন'), 'button secondary'); share.type = 'button';
  const message = node(doc, 'span', null, 'fine-print'); message.setAttribute('role', 'status');
  share.addEventListener('click', async () => {
    const url = pujaLink(p, location.origin, bn ? 'bn' : 'en');
    try {
      if (navigator.share) await navigator.share({ title: p.name, url });
      else if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(url); message.textContent = t('Link copied', 'লিঙ্ক কপি হয়েছে'); }
      else message.textContent = url;
    } catch (e) { if (e.name !== 'AbortError') message.textContent = url; }
  });
  actions.append(share, message); card.append(actions);
  card.append(link(doc, t('Report changed venue/date', 'স্থান/তারিখ সংশোধন জানান'), reportURL(p), 'profile-report'));
  card.append(node(doc, 'p', [p.last_verified_at ? `${t('Listing reviewed', 'তালিকা পর্যালোচিত')} ${p.last_verified_at.slice(0, 10)}` : '', v.checked ? `${t('Source checked', 'উৎস দেখা হয়েছে')} ${v.checked.slice(0, 10)}` : ''].filter(Boolean).join(' · '), 'fine-print'));
  if (v.pending) card.append(node(doc, 'p', t('Source change awaiting review', 'উৎসের পরিবর্তন পর্যালোচনার অপেক্ষায়'), 'fine-print'));
  const more = node(doc, 'details', null, 'profile-more'); more.append(node(doc, 'summary', t('More about this Puja', 'এই পুজো সম্পর্কে আরও')));
  if (p.year && !p.edition) more.append(node(doc, 'p', `${t('Source listing year', 'উৎসের তালিকার বছর')}: ${p.year}. ${t('This is not current-edition venue confirmation.', 'এটি বর্তমান আয়োজনের স্থানের নিশ্চয়তা নয়।')}`, 'fine-print'));
  if (!p.edition && (p.neighborhood || p.area)) more.append(node(doc, 'p', `${t('Source-listed area', 'উৎসে তালিকাভুক্ত এলাকা')}: ${p.neighborhood || p.area}`));
  if (!p.edition && p.location_precision === 'source_zone') more.append(node(doc, 'p', t('The directory area is a broad zone, not a reviewed street address.', 'ডিরেক্টরির এলাকা একটি বিস্তৃত অঞ্চল, পর্যালোচিত রাস্তার ঠিকানা নয়।'), 'fine-print'));
  if (p.about?.text) more.append(node(doc, 'p', p.about.text));
  if (p.organizer) more.append(node(doc, 'p', `${t('Organizer', 'আয়োজক')}: ${p.organizer}`));
  if (v.links.length) {
    const links = node(doc, 'ul', null, 'profile-links');
    const labels={website:t('Official website','অফিশিয়াল ওয়েবসাইট'),facebook:'Facebook',instagram:'Instagram',programme:t('Programme','অনুষ্ঠানসূচি'),contact:t('Contact','যোগাযোগ')};
    for (const l of v.links) { const li = node(doc, 'li'); li.append(link(doc, labels[l.kind] || l.kind, l.url)); links.append(li); }
    more.append(links);
  }
  if (v.notes.length) {
    more.append(node(doc, 'h4', t('Programme highlights', 'অনুষ্ঠানের সংক্ষিপ্ত তথ্য')));
    for (const note of v.notes) { const p = node(doc, 'p'); p.append(node(doc, 'strong', note.title), doc.createTextNode(` — ${note.text}${note.when ? ` · ${note.when}` : ''}`)); more.append(p); }
  }
  const provenance = node(doc, 'details'); provenance.append(node(doc, 'summary', t('Read source provenance', 'উৎসের বিবরণ')));
  const evidence = [...(p.sources || []), ...(p.edition?.evidence || []), ...(p.edition?.location?.evidence || []), ...(p.about?.evidence || []), ...v.links.map(l => l.evidence), ...v.notes.flatMap(n => n.evidence || [])];
  const seen = new Set();
  for (const s of evidence) { const key = `${s.source_url}/${s.quote}`; if (seen.has(key)) continue; seen.add(key);
    const paragraph = node(doc, 'p'); const a = link(doc, s.source_title || s.publisher, s.source_url);
    if (a) paragraph.append(a);
    paragraph.append(doc.createTextNode(s.evidence_kind === 'owner_attestation'
      ? ` — Owner review: ${s.quote}` : ` — “${s.quote}”`)); provenance.append(paragraph);
  }
  more.append(provenance); card.append(more); return card;
}
