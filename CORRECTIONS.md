# Corrections, disputes and source suggestions

## Puja and nearby food

Use the existing Google Form for missing Pujas, changed dates/venues and listing
corrections. “Suggest a Puja” and the selected profile’s “Report changed venue/date”
open the same form; no GitHub account is required. Provide the Puja name, city/region
and public source URL. Describe the correction (or nearby-food detail) in Additional
note. Do not include private information. Responses follow the existing private
Sheet and owner review process; nothing publishes automatically.

Open the Puja correction form from this page:

https://foodpath.nemoneek.com/corrections

## Food Safety Evidence — West Bengal

Use the separate private-response Food Safety source form when configured through
community_submission_url. Until then, its form is shown as coming shortly; the
corrections page also offers public, source-backed correction/source issue templates.
Never put sensitive correspondence in those public issues. No submission automatically
changes an evidence record or relaxes the evidence rules.

The public site is https://foodpath.nemoneek.com/ . The Puja suggestion form is configured
separately from Food Safety intake. No unconfigured email address or form URL is
invented. Private form responses are not published or exported by this repository.

Any public intake route must require a source URL where applicable, prohibit arbitrary uploads and unsupported allegations, and never publish submissions automatically. It must remain a controlled manual-review channel rather than a public reporting or comment system.

A correction should identify the record ID, disputed field, reason and a supporting public source URL. Optional context should avoid personal details. A source suggestion should provide URL, publisher, publication date if known, event description and a short relevant evidence span.

Do not submit unsupported allegations, harassment, discriminatory content, unnecessary personal information or private documents. GitHub controls submission account data and infrastructure logs under its policies. This repository is public: issue text is public. Do not post sensitive legal correspondence in public Issues.

## Maintainer procedure

An ordinary transport failure uses a dated source warning and bounded retries, not the hold command. Use a semantic hold for credible uncertainty, correction or harm. See METHODOLOGY.md for retry/archive thresholds and restoration. Before processing a submitted URL, admit its exact host through the source policy after review; never fetch arbitrary form input. Keep contact and internal reviewer notes outside public datasets.

1. Acknowledge and triage as capacity allows; no guaranteed response time is promised.
2. Suspend potentially inaccurate or harmful records promptly with the hold command. Do not wait for a final conclusion to reduce exposure.
3. Examine cited originals, dates, corrections and scope; seek additional authoritative public sources where needed.
4. Record a neutral outcome and changed fields. Preserve the event ID and existing history when revising a pending JSON record.
5. Use the review command only after fresh source checks and an explicit context/field attestation. Otherwise leave it pending, disputed, withdrawn, superseded or rejected.
6. Validate, build and review the Git diff before distributing an update.

Example: food-safety hold WBFS-0123456789ab --status DISPUTED --note 'Public-source context under review.'

Publication: food-safety review --file data/tmp/review.json --reviewer MAINTAINER_HANDLE --note 'Source context and attribution checked' --attest-source-context --attest-all-fields

The example ID is illustrative only. Review files must reside inside this project. Do not edit meaningful history away. Record source corrections, changed quantities, entity attribution and subsequent official outcomes explicitly. Prior snapshots are private audit material, not a reason to keep disputed claims publicly visible.

No policy promises immunity from legal responsibility. Records may be suspended or removed when accuracy or publication risk remains uncertain.
