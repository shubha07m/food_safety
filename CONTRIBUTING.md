# Contributing

Human implementation work belongs on develop. main is production and receives bounded scheduled data updates. No develop-to-main merge or production release occurs without owner approval. Before release, synchronize current production data using the maintainer procedure; never replace newer production artifacts with stale branch data. Community source/correction intake uses the configured private-response Google Form, not public Issues. GitHub remains appropriate for code contributions and non-sensitive tooling discussion.

Read DISCLAIMER.md, METHODOLOGY.md and CODE_OF_CONDUCT.md first. Contributions organize public evidence; they must not express unsupported allegations or create reputational rankings.

Use the controlled Issue Forms for public-source suggestions and corrections. While the repository remains private this requires collaborator access; the same links work publicly after the maintainer changes visibility. No Issue content automatically publishes. Forks and pull requests are welcome when access permits. Do not submit arbitrary file uploads, personal details, social-identity classifications, screenshots without public sources or full copyrighted articles.

For code: work in the food conda environment, keep all environments/caches inside this repository, keep changes focused, add meaningful regression coverage, run ruff, pytest and data validation. Fixtures must be explicitly synthetic and remain outside production display. Tests use no network or paid APIs.

For data: provide exact minimal evidence per factual field, canonical URLs, source metadata, retrieval time and clear context. Never infer date, quantity, actor or establishment attribution from ambiguous reporting. Keep unknown values. A second publisher is not independent if it republishes the same dispatch. Preserve stable IDs, revision notes and prior-version hashes.

Review commands require explicit source-context and all-fields attestations. A maintainer must check geographic scope, source terms, title/date, quote context including negation, entity/action/quantity relationships, later corrections, sensitive data and derived categories. The model and matching code cannot replace this review.

Recommended repository settings: protected main; required CI; pull-request reviews; CODEOWNERS where maintainers agree; restricted action permissions; no secrets on untrusted PRs; secret scanning and private vulnerability reports when available. Do not deploy the website merely to test a pull request.

The public beta uses a bounded two-hour schedule with a narrowly scoped deterministic publication adapter. It does not replace review of complex claims or derived context. Volunteer maintainers can help with periodic source audits, Bengali wording and safe tooling. Independent India-qualified legal review has not been completed.
