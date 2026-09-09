# Source policy and copyright

## Phase 1 source assessment (develop, 9 September 2026)

Indian Express Bangla article retrieval was accessible; its existing West Bengal index remains configured. Added Bengali discovery terms and narrow authority/location/inspection constructions, based on IE reporting vocabulary and TV9 authority terminology. Original Bengali spans remain exact; unsupported syntax/negation stays pending. TV9 Kolkata index was accessible and joins the bounded rotation. No relevant leads on a sampled index is not permission to broaden into a crawl.

KMC normal HTTPS failed its TLS handshake; FSSAI press-release/advisory responses had no extractable article content. Their official index policies remain disabled until compliant retrieval works; do not bypass TLS, robots, anti-bot or PDF limits. Telegraph's sampled index returned 403 and remains curated/manual. Anandabazar previously returned 403; its existing curated source policy does not authorize bypassing access controls. No claim is made that official-source automatic publication is operational.

Sangbad Pratidin, Ei Samay, ABP Ananda, News18 Bangla and Zee 24 Ghanta remain manual pilot candidates, not enabled crawlers. Source expansion requires a small compliant endpoint check and fixtures first. Official social-media and arbitrary document/image ingestion remain disabled.

Discovery and maintenance receive separate portions of the six-article run. At most two rotating index pages are checked. Source maintenance uses persisted per-source backoff and a per-run host circuit breaker. An outage changes availability, not historical truth; see METHODOLOGY.md for seven-day review and 30-day archive rules. No live crawling or paid models are used in CI.

The public beta contains a small source-reviewed dataset. No prototype rows or URLs are evidence. config/sources.yml defines enabled news publishers and disabled official-source starting points; configured status is not proof of an article's relevance. The live source-composition chart is computed from published supporting sources.

Source homepage: https://fssai.gov.in/
Source policies: https://fssai.gov.in/cms/website-policies.php

Add a small, specific set of curated article URLs only after checking relevance, accessible context, publisher identity, terms and robots policy. Configure exact hosts (www and apex separately). No wildcard host matching or recursive traversal is supported. Keep initial smoke runs to 1–3 articles.

Tier A means an official public authority source. Tier B means an established, identifiable news organization with accessible reporting. Tier C requires stronger corroboration and cannot enter V1 publication as supporting evidence. Discovery-only snippets, social posts and aggregators never automatically enter the dataset. Anonymous claims, WhatsApp forwards, unsupported screenshots and random social-media allegations are excluded.

A tier is a retrieval/review policy, not an endorsement or guarantee of accuracy. A publisher can issue a correction or report an allegation without establishing its truth. Syndicated copies are not independent sources.

Retain canonical URL, title, publisher, publication date if known, retrieval time, text hash, source type and the minimum exact evidence/context spans. Individual evidence quotes are capped at 25 words, contexts at 60 words, and maximal retained contexts at 250 words per canonical source, including multiple records. Do not use these caps to claim copyright compliance; context and rights remain a matter for review.

Do not republish full articles, bypass paywalls, evade robots restrictions, upload pages to archive services, or download image collections. Optional archive links must already be available and legally/technically appropriate. Third-party content remains subject to its respective rights; the repository's code license does not relicense it.

Failures go to a pending/rejected path, not public data. HTTP retrieval supports bounded HTML/plain text/XHTML and RSS/Atom XML. Compressed or image/PDF-only responses require manual assessment. Robots retrieval failures fail closed.

## Bounded discovery

The schedule checks at most two rotating configured publisher index pages, extracts only same-domain relevant links, and follows at most six article URLs. Index titles/snippets never become evidence. There is no recursive following of article links. Feed parsing is supported but no RSS feed is currently enabled: the tested TOI feed terms restrict reuse, and the tested Indian Express Bangla feed returned HTML. Enabled indexes are TOI Kolkata, Indian Express Bangla West Bengal and TV9 Kolkata. Publisher terms and robots rules still apply; an inaccessible index is reported, not bypassed.

TOI RSS terms reviewed: https://timesofindia.indiatimes.com/rss.cms

Discovery index bodies have a separate 1 MiB ceiling; article bodies remain capped
at 512 KiB. This accommodates the verified Kolkata index without changing evidence
or network-safety rules. Normal unsupported candidates are rejected without
marking a successfully completed source scan as a network failure. Source retrieval
failures and invalidated existing public support still report operational failure.
