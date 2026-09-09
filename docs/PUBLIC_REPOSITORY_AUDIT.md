# Public repository audit

Audit date: **2026-09-09**

Repository visibility: **Private**

Recommendation: **NOT READY FOR PUBLIC VISIBILITY — GitHub server-side pull-request refs must be purged and re-audited.**

This is a current audit, not a development diary. Pattern scanning is one layer of review and does not prove that a repository contains no sensitive material.

## Current tracked tree

- No tracked `.env`, private pending/rejected queue, private record history, source dump, browser profile, cache or scratch/conversation path was found.
- No known credential/private-key pattern or local workstation path was found in the current locally reachable history.
- Public deployment remains limited to `site/`; its verifier rejects private paths, unsupported file types, symlinks and common secret patterns.
- Short attributed evidence spans are retained. Full downloaded articles are not tracked or deployed.
- Author/committer email metadata in the rewritten local refs uses the maintainer's GitHub noreply address.

The machine-readable result is [reports/public_repository_audit.json](../reports/public_repository_audit.json). The audit command intentionally fails closed while the server-side gate in `config/public_repository.yml` is false.

## Local Git-history sanitation

The prior history contained private record snapshots/queues, obsolete internal utilities, the illustrative prototype, machine-specific paths and a public author email. A deterministic rewrite removed those paths across local `main` and `develop`, replaced machine paths, and normalized public author metadata.

- Old `main`: `491185b4d688777c5c13fb633d578d83367c8b34`
- Rewritten `main`: `ccae493e550e2b2d43be0031815912eb69ecdea3`
- Old `develop`: `da6fe6012fb45b607c265d27c722f8da6015954e`
- Rewritten `develop`: `1194f7509ebc6a87e9581c8eb271c544034ee3c4`
- The production `site/` tree was byte-identical before and after the rewrite.

A private recovery bundle exists only at `.cache/history-backup/food_safety-before-public-sanitize-2026-09-09.bundle`. It is ignored and must never be committed, uploaded or shared publicly.

## GitHub server-side result

The rewritten `main` and `develop` refs were force-updated using exact leases. GitHub Actions subsequently passed on both branches. The repository has no forks, no retained Actions artifacts and no Actions caches at the time of this audit; earlier run records were removed.

Seven GitHub pull-request refs (`refs/pull/1/head` through `refs/pull/7/head`) remain server-managed and read-only. Each reaches pre-rewrite content: PR 1 and PR 2 each expose one removed private-artifact path; PRs 3–7 each reach 73 private-artifact path entries. An old commit remains retrievable through GitHub while those refs/cached views exist. Ordinary force-pushing cannot delete these refs.

## Remaining blocker and owner action

Contact GitHub Support and request removal/dereferencing of the affected pull-request refs and cached commit views, followed by server-side garbage collection, using GitHub's [sensitive-data removal guidance](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository). Provide the repository name, affected PR numbers 1–7, the first affected historical commit (`eaf803d8a494d94f0b3f20f6e9d647bc4ab13f20`), and explain that the repository is intentionally still private.

After GitHub confirms completion:

1. Verify that old commit and PR-ref objects are no longer retrievable.
2. Re-run `python scripts/audit_repository.py` and a manual tree/history review.
3. Set `github_pull_refs_cleared: true` only after that verification.
4. Change visibility only after the audit reports no remaining blocker.

If GitHub cannot purge the refs, the reliable alternative is a new clean-history repository and an explicit hosting-integration change. That alternative was not taken because it would disturb the existing production integration.
