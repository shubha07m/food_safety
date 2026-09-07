# Deployment preparation — no public deployment enabled

Keep the GitHub repository private during evaluation. Public hosting is a separate decision. A private GitHub repository does not automatically make a Pages website private. Do not attach this repository to an automatically publishing service until publication is explicitly authorized.

Build in conda `food` with `python -m food_safety.cli validate` and `python -m food_safety.cli build`. The deployable output is exactly `site/`. Never deploy the repository root, `.env`, environments, pending/rejected queues or private history. The prototype is not part of the site output.

## Cloudflare Pages

After review, upload the already-built `site/` directory using the Pages dashboard's direct-upload option or configure a separately reviewed deployment job. There is no need for a server, database, framework build, cloud API or secret in the browser. The `_headers` file specifies CSP, HSTS, nosniff, no-referrer, Permissions-Policy and frame restrictions. Check the actual HTTPS responses on the chosen domain; preview and custom domains may have different settings. Do not consider a private repository an access control for an uploaded site.

The build uses Python locally; uploading prebuilt static files avoids depending on a particular cloud Python/conda image. If Git integration is later enabled, choose an equivalent reviewed build environment and publish only the generated `site/` output. Disable automatic public previews until their access policy is reviewed.

## GitHub Pages fallback

Once explicitly authorized, create a separate Pages deployment workflow that builds/validates in conda food, uploads only site/ to an official Pages artifact action, and deploys through a protected GitHub environment. This repository deliberately has no such active deployment workflow. Relative links support project subpaths.

GitHub Pages does not apply Cloudflare's `_headers`. Meta CSP provides a partial fallback, but frame-ancestors and HSTS need host-level response headers. Use a suitable proxy/host if those controls are required. Confirm Pages availability for the account's private repository plan without changing repository visibility as a workaround.

## Before broad public launch

Review the legal wording with India-qualified counsel; individually verify the small initial dataset; test the correction/suspension procedure; establish a correction channel accessible to affected parties; inspect all repository history and Issues before any visibility change; set branch protections and security reporting; inspect HTTPS/security headers; confirm no private files or model keys exist in the output; and update the evaluation status/robots policy only after authorization.

Do not enable schedule, AUTO_PUBLISH, repository visibility or public hosting merely because CI passes. No test establishes legal compliance or immunity.
