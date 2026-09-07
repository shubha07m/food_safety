# Initial dataset quality report

Generated after a bounded, manual source-review run on 2026-09-07 UTC.

## Scope and decision

The review began with nine candidate publisher URLs. Seven direct articles from
three enabled Tier-B publishers were accessible through the tracker’s
robots-aware fetcher and produced source-supported records. One Moneycontrol
URL returned HTTP 403 and one Siliguri Times URL had no extractable article;
both were excluded. Discovery-only and aggregator material was not published.

The resulting 35 published records are below the aspirational 50–75 range.
The review stopped at this defensible count rather than treating broad totals,
unidentified outlets, inaccessible pages, or repeat coverage as distinct
establishment events.

## Dataset diagnostics

| Measure | Result |
| --- | ---: |
| Candidate articles checked | 9 |
| Accepted source articles | 7 |
| Published records | 35 |
| Pending records | 0 |
| Rejected/inaccessible candidate URLs | 2 |
| Duplicate records published | 0 |
| Publishers represented | 3 |
| Cross-source verified records | 0 |
| Source-verified, single-publisher records | 35 |
| Unique canonical source URLs | 7 |
| Areas represented | 25 |
| Source publication-date range | 2026-09-03 to 2026-09-07 |
| LLM/VLM calls | 0 / 0 |

### Accepted records by publisher

| Publisher | Records |
| --- | ---: |
| The Times of India | 25 |
| Business Today | 5 |
| TV9 Bangla | 5 |

### Records by source publication date

| Date | Records |
| --- | ---: |
| 2026-09-03 | 11 |
| 2026-09-04 | 7 |
| 2026-09-05 | 7 |
| 2026-09-06 | 7 |
| 2026-09-07 | 3 |

### Context completeness

All 35 records retain unknown derived menu category and ownership/context
category. This is intentional: no independent business, owner, menu, or social
identity inference was added. Action grouping is `other` unless it can be
directly and conservatively derived from the source; the dashboard remains
evidence-first and rows remain available behind every aggregate.

## Review controls applied

Each published record was freshly fetched, linked to a configured Tier-B source,
assigned a publication date from that source, and checked against a short exact
text span plus the extracted-text hash. Records use `SOURCE VERIFIED`, which
means the cited page and displayed source statement were checked; it is not an
independent finding about an establishment or event. No live crawling, browser
automation, LLM, VLM, or automatic publication was used. `AUTO_PUBLISH` remains
false.

## Known limitations and next review batch

The first batch is source-concentrated and uses publication dates where a source
did not make the calendar date of the event explicit. It should not be read as
an official total or representative sample. The next batch should seek direct,
accessible authority material and independently reported Tier-B coverage before
adding cross-source associations or more records.
