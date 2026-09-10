# Security policy

## Structured extraction boundary

Article text is untrusted data, including prompt-like instructions. The extractor has no tools, browser session, publication permission or configurable destination supplied by article text. The hosted adapter uses a fixed HTTPS endpoint, a header-held credential, bounded input/output, a 20-second timeout, no redirects and no automatic retries. Provider errors are reduced to controlled codes; article bodies and credentials are not logged. A schema-valid answer still needs independent span, semantic, source and publication validation. Source lifecycle checks do not consume model output.

Shadow/evaluation/exception artifacts stay under ignored `.cache/llm_eval/`; do not upload them as GitHub artifacts or include them in deployments. Tests remove live credentials. No model token or runtime inference is present in the static frontend. Provider billing limits remain an owner responsibility; local spend estimates are not a billing guarantee.

The project keeps static deployment. Community intake is an outbound link to a validated HTTPS Google Forms URL, never an embedded public write endpoint. Submitted URLs must separately pass publisher admission and SSRF controls. The optional local CSV importer retains only an allowed source URL and submission type; no raw form response, contact, or reviewer note is public. Retry-After and host failure limits prevent aggressive retries; no anti-bot/TLS bypass is allowed. A source warning never relaxes new-record admission. develop cannot dispatch production ingestion; hosting remains unchanged.

The public site is static HTML/CSS/JavaScript and generated public JSON. There is no public admin endpoint, database write API, login, executable submission content, comments, arbitrary upload or SQL backend. Only the site/ directory may be deployed, after review. Never serve the repository root: it contains private pending/history/configuration.

## Safeguards

The frontend creates source-derived nodes with textContent; it never inserts scraped HTML. External URLs are limited to http/https, with credentials/private literals rejected; external links use noopener noreferrer. No third-party scripts/fonts/CDNs are loaded. CSV formula prefixes are escaped.

Fetches require configured exact domains. DNS results are checked for global addresses and connections are pinned to an approved IP while TLS still verifies the original hostname. This avoids a second DNS lookup during connection. Redirects recheck domains, DNS, schemes and robots policy. Private/local/metadata addresses, unusual ports, URL credentials and HTTPS downgrades are rejected. No proxy environment is used. Timeout, response size, redirect, article and per-source caps apply. DNS resolution uses the operating system and can outlast the socket timeout; production network egress controls are an additional recommended layer. No arbitrary source text becomes shell commands.

Cloudflare _headers supplies CSP, frame-ancestors none, nosniff, no-referrer, restrictive permissions and HTTPS HSTS. The HTML also has a CSP meta fallback for local/GitHub Pages use. HSTS and frame-ancestors require actual HTTP response headers; GitHub Pages cannot apply _headers. Use Cloudflare or an appropriate front proxy if those controls are required. Confirm headers on the final custom domain. Local Python http.server is for loopback development only.

Dependencies are pinned and CI includes a lightweight audit. Dependabot proposes updates. Actions use immutable SHAs. CI has read-only contents permission and never receives model keys, runs a crawler or consumes paid tokens on PRs. Refresh Food Safety Data runs approximately every two hours or by authenticated manual dispatch. Only that job has contents-write permission; it commits an explicit public-artifact allowlist after tests and validation. It does not upload private queues or snapshots. There is no push-triggered source scan or public refresh endpoint.

## Reporting

Do not put credentials, exploit details or private data in public Issues. Use GitHub private vulnerability reporting when available, or coordinate privately with a repository maintainer. No separate security mailbox has been configured; do not invent one. Acknowledge reports as capacity permits and publish a minimal advisory when appropriate.

## Maintainer operations

Keep .env and model secrets out of commits and frontend assets. Avoid logging exception bodies or environment variables. Review all action/config/dependency changes. Recommend protected main, required CI, restricted direct pushes, secret scanning where available and tightly scoped deployment tokens. GitHub Free does not expose branch-protection rules for this private repository; enable required CI, block force pushes and block deletion immediately if the plan changes or the repository becomes eligible. A single-maintainer project should not require multiple human approvals.

An interrupted data transaction blocks validation and site build. Inspect data/.transaction.json and Git diffs, preserve any useful audit snapshots, restore the last reviewed coherent data set, then remove only that marker after review. Never automatically delete a marker or force a build through inconsistent data.

A partial failed scan can add source-availability warnings or eventually archive prolonged unverifiability; transport failure alone does not semantically suspend evidence. The last-successful timestamp does not advance on failure. Cloudflare Git integration deploys validated static artifacts from main.
