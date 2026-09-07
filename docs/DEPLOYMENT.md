# Deployment preparation — no public deployment enabled

Keep the GitHub repository private during evaluation. Public hosting is a separate decision. A private GitHub repository does not automatically make a Pages website private. Do not attach this repository to an automatically publishing service until publication is explicitly authorized.

Build in conda `food` with `python -m food_safety.cli validate` and `python -m food_safety.cli build`. The deployable output is exactly `site/`. Never deploy the repository root, `.env`, environments, pending/rejected queues or private history. The prototype is not part of the site output.

## Cloudflare Pages

After explicit authorization, upload the already-built `site/` directory using the Pages dashboard's direct-upload option, or run `scripts/release_public_beta.sh --confirm-public-release --deploy-cloudflare` from a maintainer machine with Cloudflare authentication. There is no server, database, framework build, cloud API or secret in the browser. The `_headers` file specifies CSP, HSTS, nosniff, no-referrer, Permissions-Policy and frame restrictions. Check actual HTTPS responses on the chosen domain; preview and custom domains may differ. Do not consider a private repository an access control for an uploaded site.

For Pages, use `site/` as the output directory; never deploy the repository root. Connect the private repository only if the account plan permits it and automatic public previews have been reviewed. Keep Cloudflare account credentials outside the repository. Use a preview first, verify `scripts/verify_public_output.py`, test correction and data-download links, then promote or roll back from the Pages dashboard.

The build uses Python locally; uploading prebuilt static files avoids depending on a particular cloud Python/conda image. If Git integration is later enabled, choose an equivalent reviewed build environment and publish only the generated `site/` output. Disable automatic public previews until their access policy is reviewed.

## GitHub Pages fallback

Once explicitly authorized, create a separate Pages deployment workflow that builds/validates in conda food, uploads only site/ to an official Pages artifact action, and deploys through a protected GitHub environment. This repository deliberately has no such active deployment workflow. Relative links support project subpaths.

GitHub Pages does not apply Cloudflare's `_headers`. Meta CSP provides a partial fallback, but frame-ancestors and HSTS need host-level response headers. Use a suitable proxy/host if those controls are required. Confirm Pages availability for the account's private repository plan without changing repository visibility as a workaround.

## Before broad public launch

Review the legal wording with India-qualified counsel; individually verify the small initial dataset; test the correction/suspension procedure; establish a correction channel accessible to affected parties; inspect all repository history and Issues before any visibility change; set branch protections and security reporting; inspect HTTPS/security headers; confirm no private files or model keys exist in the output; and update the evaluation status/robots policy only after authorization.

Do not enable schedule, AUTO_PUBLISH, repository visibility or public hosting merely because CI passes. No test establishes legal compliance or immunity.
