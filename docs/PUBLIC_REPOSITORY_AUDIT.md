# Public repository audit

Audit date: **2026-09-11**

Repository visibility: **Public**

Recommendation: **ROUTINE AUDIT PASSED**

This is a bounded pattern and path audit, not proof that no sensitive material exists. It distinguishes publication history controlled by the repository maintainers from GitHub-managed pull-request refs.

## Controlled publication history

`local_history_sanitized` covers the current tracked tree and locally reachable `refs/heads/*` and `refs/tags/*`. It does not use `git rev-list --all`, because that would conflate maintained publication history with stashes or hosting-provider refs.

The current scan found:

- no tracked or historical private queue/cache paths;
- no credential/private-key pattern;
- no local workstation path; and
- no private source dump in controlled history.

Non-noreply author email metadata is reported separately and is not classified as a repository-content sanitation failure. Contributors should still prefer GitHub noreply addresses when they do not intend to publish an email address.

## GitHub-managed pull refs

GitHub currently retains **8** `refs/pull/*/head` refs. They are normal server-managed contribution metadata and cannot be removed through ordinary branch maintenance. Their presence is reported through `affected_pull_refs` and `github_pull_refs_cleared`; it does not by itself make `local_history_sanitized` false or fail routine CI.

When pull refs are locally available, the audit scans their reachable content separately. Any private path, credential pattern or workstation path found there sets `pull_ref_sensitive_content_found: true` and fails `audit_passed`. A checkout that does not contain server-side pull refs cannot attest to their contents; the configured count remains an informational server-side inventory.

## Other checks

- Public deployment remains limited to `site/`; its verifier rejects private paths, unsupported file types, symlinks and common secret patterns.
- Full downloaded articles, private submissions and LLM caches are not tracked or deployed.
- No retained Actions artifacts are recorded in the current configuration.
- The machine-readable result is [reports/public_repository_audit.json](../reports/public_repository_audit.json).

The audit exits successfully when controlled history is sanitized and no locally available pull ref contains a sensitive-content finding. `github_pull_refs_cleared: false` remains visible information, not a claim that GitHub deleted those refs.
