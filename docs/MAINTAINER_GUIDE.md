# Maintainer guide

Keep routine maintenance small and evidence-led.

1. Trigger **Review source update** from the private GitHub Actions interface, or let the bounded six-hour schedule run.
2. Review the retained artifact. Treat every candidate as pending until a maintainer checks source context, duplication, sensitive-data rules and evidence spans.
3. Approve, revise, suspend or reject through the existing CLI/review workflow; rebuild and push only reviewed changes.

`AUTO_PUBLISH=false` is intentional. Scheduled work never grants a public record a finding, ranking or safety meaning. The public site has no refresh endpoint; workflow dispatch is available only to repository maintainers.

Before a release, use `docs/PUBLIC_RELEASE_CHECKLIST.md`, then run `scripts/release_public_beta.sh --confirm-public-release`. Add `--deploy-cloudflare` only after explicit authorization and configured Cloudflare credentials.
