#!/usr/bin/env bash
set -euo pipefail

if [[ "${1:-}" != "--confirm-public-release" ]]; then
  echo "Refusing release. Re-run with --confirm-public-release after completing docs/PUBLIC_RELEASE_CHECKLIST.md."
  exit 2
fi
if [[ "${2:-}" == "--deploy-cloudflare" ]]; then
  deploy=true
elif [[ -n "${2:-}" ]]; then
  echo "Unknown option: $2"
  exit 2
else
  deploy=false
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Refusing release: git worktree is not clean."
  exit 1
fi

python -m ruff check .
python -m pytest -q --basetemp=.cache/pytest-release
node --test tests/site_data.test.mjs
python -m food_safety.cli validate
python -m food_safety.cli build
python scripts/verify_public_output.py

if [[ "$deploy" == true ]]; then
  command -v wrangler >/dev/null || { echo "Cloudflare deployment requested but wrangler is unavailable."; exit 1; }
  : "${CLOUDFLARE_ACCOUNT_ID:?Set CLOUDFLARE_ACCOUNT_ID for explicit deployment.}"
  wrangler pages deploy site --project-name food-safety-evidence-tracker --branch main
else
  echo "Release gates passed. No deployment was attempted. Use --deploy-cloudflare only after explicit authorization."
fi
