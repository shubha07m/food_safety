# Repository audit procedure

This is a bounded pattern/path audit, not proof of absence of sensitive material.
Run it against the current checkout; dated reports are snapshots, not current
certification.

~~~sh
python scripts/audit_repository.py --no-write
python scripts/verify_public_output.py
python scripts/stage_generated.py
~~~

## Controlled history and current output

`local_history_sanitized` covers tracked content and reachable maintained branches
and tags. The report distinguishes history from the current tree. A clean current
output does not establish that historical checks pass. Non-noreply author metadata
is reported separately; prefer intentional public attribution metadata.

Tracked `site/maps-config.json` must be blank. Current checkout/index guards reject
populated configuration and credential-shaped values. Runtime artifact validation
permits only the designated browser configuration in ignored `dist/site/`, never
private operator values. Deploy only that isolated artifact.

Source snapshots, raw provider responses, local notes, caches and operational ledgers
must stay ignored. Public JSON retains only its allowed provenance/data contract.

## GitHub-managed pull refs

Retained `refs/pull/*` are server-managed contribution metadata. Their existence is
reported separately through `affected_pull_refs` and `github_pull_refs_cleared`;
it does not alone fail controlled-history sanitation.

Locally available pull refs are scanned separately. Actual sensitive-content findings
remain blocking. A checkout without those refs cannot attest to their content;
a configured server-side inventory is informational, not a live content scan.

## Reading results

Inspect exit status and each finding category. `audit_passed` requires sanitized
controlled history and no detected sensitive content in locally available pull refs.
Do not silently suppress historical findings to pass a release gate.
The versioned [report](../reports/public_repository_audit.json) may predate current
work; rerun before relying on it. `--no-write` inspects without replacing that report.

Public-output verification also checks private paths, file types, symlinks and bounded
patterns. Runtime checks, dependency audit and browser tests are complementary—not
substitutes for history review. See [current controls](../SECURITY.md) and
[release checklist](PUBLIC_RELEASE_CHECKLIST.md).
