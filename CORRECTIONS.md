# Corrections, disputes and source suggestions

Use the repository's Request a correction or Suggest a source Issue Form when repository access is available. The website constructs links from the configured repository URL. No submitted Issue automatically changes a record or enters the dataset.

During private evaluation, only invited GitHub collaborators can access Issues. The correction flow is not publicly reachable yet. Before public launch, establish an accessible correction channel and review it with counsel. Do not promote the site while affected parties have no practical correction route. No public launch is enabled by this build.

A correction should identify the record ID, disputed field, reason and a supporting public source URL. Optional context should avoid personal details. A source suggestion should provide URL, publisher, publication date if known, event description and a short relevant evidence span.

Do not submit unsupported allegations, harassment, discriminatory content, unnecessary personal information or private documents. GitHub controls submission account data and infrastructure logs under its policies. Issue text may become visible if the repository later becomes public; keep all submissions suitable for public review. Do not post sensitive legal correspondence in public Issues.

## Maintainer procedure

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
