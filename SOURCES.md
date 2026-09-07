# Source policy and copyright

The initial production dataset is empty. No prototype rows or URLs are treated as sources. config/sources.yml contains two disabled host entries for the same official publisher, FSSAI. These are configuration starting points, not a statement that relevant West Bengal articles have been validated.

Source homepage: https://fssai.gov.in/
Source policies: https://fssai.gov.in/cms/website-policies.php

Add a small, specific set of curated article URLs only after checking relevance, accessible context, publisher identity, terms and robots policy. Configure exact hosts (www and apex separately). No wildcard host matching or recursive traversal is supported. Keep initial smoke runs to 1–3 articles.

Tier A means an official public authority source. Tier B means an established, identifiable news organization with accessible reporting. Tier C requires stronger corroboration and cannot enter V1 publication as supporting evidence. Discovery-only snippets, social posts and aggregators never automatically enter the dataset. Anonymous claims, WhatsApp forwards, unsupported screenshots and random social-media allegations are excluded.

A tier is a retrieval/review policy, not an endorsement or guarantee of accuracy. A publisher can issue a correction or report an allegation without establishing its truth. Syndicated copies are not independent sources.

Retain canonical URL, title, publisher, publication date if known, retrieval time, text hash, source type and the minimum exact evidence/context spans. Individual evidence quotes are capped at 25 words, contexts at 60 words, and maximal retained contexts at 250 words per canonical source, including multiple records. Do not use these caps to claim copyright compliance; context and rights remain a matter for review.

Do not republish full articles, bypass paywalls, evade robots restrictions, upload pages to archive services, or download image collections. Optional archive links must already be available and legally/technically appropriate. Third-party content remains subject to its respective rights; the repository's code license does not relicense it.

Failures go to a pending/rejected path, not public data. V1 fetches text/html, text/plain and XHTML only. Compressed or image/PDF-only responses require later manual assessment. Robots retrieval failures fail closed.
