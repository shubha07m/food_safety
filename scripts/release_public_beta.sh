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

food_python=.conda/envs/food/bin/python
test -x "$food_python" || { echo "Project-local food environment is required."; exit 1; }
"$food_python" -m ruff check .
"$food_python" -m pytest -q --basetemp=.cache/pytest-release
node --test tests/*.test.mjs
"$food_python" -m food_safety.cli validate
"$food_python" -m food_safety.cli build
"$food_python" scripts/verify_public_output.py

if [[ "$deploy" == true ]]; then
  echo "The live site deploys through the authorized Cloudflare Workers Git integration. Push validated artifacts to main; no local token or direct deployment is used."
  exit 2
else
  echo "Validation gates passed. No deployment or repository visibility change was attempted."
fi
