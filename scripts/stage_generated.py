"""Validate checkout/index configuration and stage an explicit generated-file set."""

import argparse
import json
import subprocess
from pathlib import Path

from audit_repository import SECRET

ROOT = Path(__file__).resolve().parents[1]
GENERATED = (
    "data/osm_food_london.json",
    "site/data/osm_food_london.json",
    "data/food_provider_london.json",
    "site/data/food_provider_london.json",
    "data/osm_food_toronto.json",
    "site/data/osm_food_toronto.json",
    "data/food_provider_toronto.json",
    "site/data/food_provider_toronto.json",
    "data/osm_food_melbourne.json",
    "site/data/osm_food_melbourne.json",
    "data/food_provider_melbourne.json",
    "site/data/food_provider_melbourne.json",
    "data/regions.json",
    "site/data/regions.json",
    "data/osm_food_california.json",
    "site/data/osm_food_california.json",
    "data/food_provider_california.json",
    "site/data/food_provider_california.json",
    "data/events.json",
    "data/events.csv",
    "data/events.csv.metadata.json",
    "data/status.json",
    "data/retired.json",
    "data/source_checks.json",
    "data/pandals.json",
    "data/puja_refresh.json",
    "data/osm_food.json",
    "data/food_provider.json",
    "site/data/osm_food.json",
    "site/data/food_provider.json",
    "site/data/events.json",
    "site/data/events.csv",
    "site/data/events.csv.metadata.json",
    "site/data/aggregates.json",
    "site/data/locations.json",
    "site/data/retired.json",
    "site/data/lifecycle.json",
    "site/data/compliance.json",
    "site/data/pandals.json",
    "site/data/places.json",
    "site/status.json",
    "site/repository.json",
    "site/policies/disclaimer.html",
    "site/policies/methodology.html",
    "site/policies/corrections.html",
    "site/policies/privacy.html",
    "site/policies/sources.html",
    "site/policies/data_dictionary.html",
    "site/policies/contributing.html",
)


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root)


def check(root, *, index=True):
    """Inspect actual bytes, including unchanged indexed files; report paths only."""
    paths = git(root, "ls-files", "-z").decode().split("\0")
    failures = set()
    for path in filter(None, paths):
        local = root / path
        bodies = [("checkout", local.read_bytes())] if local.is_file() else []
        if index:
            bodies.append(("index", git(root, "show", f":{path}")))
        for origin, body in bodies:
            invalid = bool(SECRET.search(body))
            if path == "site/maps-config.json":
                try:
                    invalid |= json.loads(body) != {"browser_key": ""}
                except (ValueError, UnicodeDecodeError):
                    invalid = True
            if invalid:
                failures.add(f"{origin}:{path}")
    if "site/maps-config.json" not in paths:
        failures.add("missing tracked browser configuration")
    if failures:
        raise ValueError("Repository configuration check failed: " + ", ".join(sorted(failures)))


def stage(root):
    check(root)
    existing = [path for path in GENERATED if (root / path).is_file()]
    git(root, "add", "--", *existing)
    changed = set(git(root, "diff", "--cached", "--name-only").decode().splitlines())
    if changed - set(GENERATED):
        raise ValueError("Generated commit contains paths outside the allowlist")
    check(root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", action="store_true")
    args = parser.parse_args()
    try:
        stage(ROOT) if args.stage else check(ROOT)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    print("Repository configuration and generated-file boundary passed")


if __name__ == "__main__":
    main()
