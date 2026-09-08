# Maintenance

**Normally: do nothing.** GitHub checks configured sources approximately every two hours. Clean candidates passing the strict automatic adapter may publish; uncertain candidates do not. Cloudflare redeploys validated public artifacts committed to `main`.

**Manual refresh:** GitHub → Actions → **Refresh Food Safety Data** → Run workflow. Only authorized repository collaborators can dispatch it. There is no public refresh button or token.

**Occasional audit:** inspect a handful of new records, original sources and the last successful refresh. Check GitHub/Cloudflare failures. No growth can simply mean no eligible new evidence; do not loosen validation to generate activity.

**Correction:** suspend promptly when needed with `python -m food_safety.cli hold RECORD_ID --note 'Neutral reason'`. Build, validate and push the safe public changes. Review a corrected record with the existing `review` command and its explicit source-context attestations. Issue submissions never publish automatically.

Private local queues/snapshots are ignored and are not uploaded as Actions artifacts. Scheduled uncertain candidates are skipped at job end; public suspension tombstones persist. For deeper inspection, run a small local refresh in `food`, then `python -m food_safety.cli pending`.

During a source-policy or accuracy incident, disable the refresh workflow in GitHub Actions. Restore it only after validation. See [deployment and rollback](DEPLOYMENT.md). Legal review remains outstanding; this guide is not legal advice.
