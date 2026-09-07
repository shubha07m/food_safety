# Public beta release checklist

Use this checklist immediately before the explicit `--confirm-public-release` action. A passing test suite is necessary but does not establish legal compliance or suitability for public promotion.

## Legal and policy

- [ ] India-qualified counsel has reviewed the final disclaimer and methodology wording.
- [ ] The correction/contact route is publicly reachable and has been tested without publishing a record.
- [ ] Privacy, correction, contribution and code-of-conduct policies are current.
- [ ] No unresolved high-risk, disputed or unsupported records remain published.

## Data

- [ ] Representative links from every publisher were manually checked.
- [ ] Source concentration and cross-source coverage are displayed honestly.
- [ ] Duplicate review is complete; no syndicated copy is marked independent.
- [ ] Missingness, map coverage and location precision are visible.
- [ ] Every non-unknown menu or business-format field has reviewed supporting evidence.

## Security and hosting

- [ ] Only `site/` is selected as the Cloudflare Pages output directory.
- [ ] Preview deployment passes header, CSP, mobile and keyboard checks.
- [ ] HTTPS headers, including CSP, HSTS, nosniff, no-referrer and framing controls, are checked on the actual domain.
- [ ] No secret, pending queue, rejected record, history archive or run artifact is publicly reachable.
- [ ] Cloudflare credentials are maintainer secrets, never frontend values.

## UX and operations

- [ ] Disclaimer, correction route and volunteer callout are visible on desktop and mobile.
- [ ] Chart filters, map points, data downloads and record details work.
- [ ] Scheduled scan remains bounded and `AUTO_PUBLISH=false`.
- [ ] Maintainers can access workflow-dispatch and review artifacts.
- [ ] Rollback procedure is understood and a prior Pages deployment is available.
