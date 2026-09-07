# Security policy

V1 is static HTML/CSS/JavaScript and generated public JSON. There is no public admin endpoint, database write API, login, executable submission content, comments, arbitrary upload or SQL backend. Only the site/ directory may be deployed, after review. Never serve the repository root: it contains private pending/history/configuration.

## Safeguards

The frontend creates source-derived nodes with textContent; it never inserts scraped HTML. External URLs are limited to http/https, with credentials/private literals rejected; external links use noopener noreferrer. No third-party scripts/fonts/CDNs are loaded. CSV formula prefixes are escaped.

Fetches require configured exact domains. DNS results are checked for global addresses and connections are pinned to an approved IP while TLS still verifies the original hostname. This avoids a second DNS lookup during connection. Redirects recheck domains, DNS, schemes and robots policy. Private/local/metadata addresses, unusual ports, URL credentials and HTTPS downgrades are rejected. No proxy environment is used. Timeout, response size, redirect, article and per-source caps apply. DNS resolution uses the operating system and can outlast the socket timeout; production network egress controls are an additional recommended layer. No arbitrary source text becomes shell commands.

Cloudflare _headers supplies CSP, frame-ancestors none, nosniff, no-referrer, restrictive permissions and HTTPS HSTS. The HTML also has a CSP meta fallback for local/GitHub Pages use. HSTS and frame-ancestors require actual HTTP response headers; GitHub Pages cannot apply _headers. Use Cloudflare or an appropriate front proxy if those controls are required. Confirm headers on the final custom domain. Local Python http.server is for loopback development only.

Dependencies are pinned and CI includes one lightweight dependency audit. Dependabot proposes updates. Actions use immutable commit SHAs. CI has read-only contents permission and never receives model keys, runs a crawler, or consumes paid tokens on PRs. The update workflow is manual-only until a maintainer enables the commented 6-hour schedule. It uploads private review artifacts rather than committing/deploying automatically.

## Reporting

Do not put credentials, exploit details or private data in public Issues. Enable GitHub private vulnerability reporting before a public launch, or coordinate privately with a repository maintainer during private evaluation. No separate security mailbox has been configured; do not invent one. Acknowledge reports as capacity permits and publish a minimal advisory when appropriate.

## Maintainer operations

Keep .env and model secrets out of commits and frontend assets. Avoid logging exception bodies or environment variables. Review all action/config/dependency changes. Recommend protected main, required CI, at least one independent review, restricted direct pushes, secret scanning where available and tightly scoped deployment tokens.

An interrupted data transaction blocks validation and site build. Inspect data/.transaction.json and Git diffs, preserve any useful audit snapshots, restore the last reviewed coherent data set, then remove only that marker after review. Never automatically delete a marker or force a build through inconsistent data.

A partial failed scan can suspend records and still generate a safe updated local site. CI update artifacts record the run failure and must not be treated as proof of freshness. No public deployment is performed by this repository's workflows.
