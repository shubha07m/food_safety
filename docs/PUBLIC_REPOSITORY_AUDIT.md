# Public repository audit

The site is already public. Repository visibility remains a separate, explicit
maintainer decision. This pass does not change it or rewrite shared Git history.

## Current-tree safeguards

- Private `data/history/`, `data/pending.json`, `data/rejected.json`, caches,
  downloads, browser profiles, environment files and local environments are ignored.
- Public deployment is limited to `site/`. Its gate checks schema, dataset equality,
  public statuses, forbidden paths, symlinks, extensions and common secret patterns.
- Refresh commits are restricted to approved datasets, public tombstones, status and
  `site/`. Private Actions review-artifact uploads have been removed.
- Source material is limited to short attributed evidence spans; no full articles
  are deployed. The original illustrative prototype remains a reference, not data.

## Historical visibility blocker

Private record snapshots were committed in earlier revisions, including `709a6b5`
and `717083d`. The latest tree had 58 snapshot files plus two queues; the complete
locally available history contains 94 distinct private-artifact paths. A bounded
scan of 233 historical blobs (about 1.8 MB) found no known token/private-key
patterns, but did find an older README with machine-specific paths. This is not
a guarantee that historical content is suitable for public release.
Removing these paths from the latest tree does **not** remove them
from Git history, existing clones or prior GitHub Actions artifacts.

Before making this repository public, explicitly resolve that history: either
approve a coordinated history rewrite removing the private paths across all refs,
or publish a clean-history export after reviewing its contents. Preserve a private
backup first. Do not casually force-push an active repository. Review previous
Actions artifacts/logs and Git commit author contact metadata before visibility
changes. A regex secret scan is not a guarantee that no private material exists.

No repository-visibility change or destructive history rewrite is performed here.
This is a publication decision, not a request for another feature-development phase.

GitHub Actions artifact inventory during this pass: no retained artifacts. The
repository remained private, main was the only branch, and no open PRs were present.
