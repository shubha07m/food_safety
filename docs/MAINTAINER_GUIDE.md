# Maintenance

**Normally: monitor occasional notifications and audit records periodically.** GitHub checks configured sources approximately every two hours. Clean candidates passing the strict automatic adapter may publish; uncertain candidates do not. Cloudflare redeploys validated public artifacts committed to `main`.

## main / develop discipline

main is production; develop is human code development. CI checks both; the refresh job explicitly runs only on main. Existing Cloudflare deployment remains unchanged. Do not merge develop without owner approval.

Release procedure: fetch origin; merge latest origin/main into develop; preserve newer production-generated data as migration inputs; run migrate, reconcile reviewed recovery changes with any new production holds, build and test. Inspect timestamps and conflicting record changes individually. Never resolve generated-data conflicts wholesale with "ours" or "theirs" or overwrite newer production data with stale exports. The bot can advance main during review: fetch again immediately before requesting release approval. No force pushes. Any required-PR protection must account for the validated production-data bot explicitly.

## Private Google Form — owner setup

Title: **The Bengal FoodPath — Source & Correction Intake**.

Description: **Independent public-source research, not an allegation or restaurant-review platform. Responses remain private to maintainers and never publish automatically. Send public URLs only. Do not include personal information, private documents, files, harassment or unsupported allegations.**

| Question | Type | Required |
| --- | --- | --- |
| Public source URL | Short answer; validate http/https URL syntax | Yes |
| Submission type | Dropdown: inspection / safety evidence; licensing / compliance document; correction; missing source | Yes |
| Establishment / area | Short answer | No |
| Existing record ID | Short answer | No |
| Short note | Paragraph, at most 600 characters | No |
| Safety acknowledgement | Checkbox: I supplied a public source, no private information or unsupported allegations, and understand that submission does not mean publication. | Yes |

Settings: no file-upload questions; no email collection; no public response summaries/results; no organization-only responder restriction if public access is intended. Do not enable a one-response limit that unnecessarily requires sign-in. Link responses to a **Restricted** Google Sheet accessible only to designated maintainers, never a published Sheet. Owner notifications are optional. Review monthly; remove spam and unnecessary personal data. Never copy raw responses, editor links or contact details into Git.

Publish the responder form and provide the **responder URL**, either forms.gle/... or docs.google.com/forms/d/e/.../viewform. Do not provide an edit URL or response Sheet URL. Set community_submission_url in config/pipeline.yml, build and test on develop, then request release approval. Without it, the site says "Submission form coming shortly" and shows no invented queue count.

In the private Sheet, track pending / approved-for-processing / rejected and a neutral reason. Approval admits a source to normal validation, not publication. Review publisher identity, terms, public URL and exact allowed host before retrieval. Export approved rows to `data/tmp/approved_form_responses.csv`, then run `python scripts/import_community_leads.py data/tmp/approved_form_responses.csv`. The importer retains only source URL and submission type in an ignored local queue; it does not retain contact or note fields. No public endpoint or backend is added.

## Lifecycle operations

Transport failures warn/retry rather than use hold. Inspect persisted data/source_checks.json review_due signals and minimal archived status after the 30-day revalidation deadline. Clear a semantic hold only with fresh source checks and explicit human attestations. Private pending bodies are not retained by scheduled runners; minimal tombstones and source diagnostics are. To review a prior published record, recover its last approved Git revision locally and preserve the later tombstone/history transition. Never publish private snapshots.

Run `python -m food_safety.cli migrate` after an announced additive schema upgrade, then validate/build. Never restore semantic holds without reviewing eligibility.

**Manual refresh:** GitHub → Actions → **Refresh Food Safety Data** → Run workflow. Only authorized repository collaborators can dispatch it. There is no public refresh button or token.

**Occasional audit:** inspect a handful of new records, original sources and the last successful refresh. Check GitHub/Cloudflare failures. No growth can simply mean no eligible new evidence; do not loosen validation to generate activity.

**Correction:** suspend promptly when needed with `python -m food_safety.cli hold RECORD_ID --note 'Neutral reason'`. Build, validate and push the safe public changes. Review a corrected record with the existing `review` command and its explicit source-context attestations. Issue submissions never publish automatically.

Private local queues/snapshots are ignored and are not uploaded as Actions artifacts. Scheduled uncertain candidates are skipped at job end; public suspension tombstones persist. For deeper inspection, run a small local refresh in `food`, then `python -m food_safety.cli pending`.

During a source-policy or accuracy incident, disable the refresh workflow in GitHub Actions. Restore it only after validation. See [deployment and rollback](DEPLOYMENT.md). Legal review remains outstanding; this guide is not legal advice.
