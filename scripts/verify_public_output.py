"""Fail-closed audit of the exact static directory eligible for publication."""

import argparse
import json
import re
from pathlib import Path

from food_safety.build import validate

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REQUIRED = [
    "index.html",
    "disclaimer.html",
    "methodology.html",
    "corrections.html",
    "data.html",
    "data/events.json",
    "data/events.csv",
    "data/events.csv.metadata.json",
    "data/pandals.json",
    "maps-config.json",
    "assets/puja/puja_hero.webp",
    "_headers",
]
FORBIDDEN = [".env", "data/pending.json", "data/rejected.json", "data/history", "data/runs"]


def main(*, runtime=False) -> None:
    validate(ROOT)
    from food_safety.browser_maps import browser_config

    expected_maps = browser_config(ROOT) if runtime else {"browser_key": ""}
    from food_safety.browser_maps import configured_key

    private_values = [
        configured_key(ROOT, name) for name in ("GOOGLE_MAPS_API_KEY", "GEMINI_API_KEY")
    ]
    missing = [name for name in REQUIRED if not (SITE / name).is_file()]
    present = [name for name in FORBIDDEN if (SITE / name).exists()]
    headers = (SITE / "_headers").read_text(encoding="utf-8")
    required_headers = [
        "Content-Security-Policy",
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "frame-ancestors",
    ]
    absent_headers = [header for header in required_headers if header not in headers]
    dataset = json.loads((SITE / "data/events.json").read_text(encoding="utf-8"))
    if dataset != json.loads((ROOT / "data/events.json").read_text()):
        present.append("public and approved datasets differ")
    if any(
        r["verification_status"] not in {"SOURCE VERIFIED", "CROSS-SOURCE VERIFIED"}
        or r.get("is_fixture")
        for r in dataset["records"]
    ):
        present.append("non-public record marker in events.json")
    allowed_data = {
        "events.json",
        "events.csv",
        "events.csv.metadata.json",
        "aggregates.json",
        "locations.json",
        "retired.json",
        "lifecycle.json",
        "compliance.json",
        "places.json",
        "pandals.json",
        "osm_food.json",
        "food_provider.json",
    }
    places = SITE / "data/places.json"
    osm = SITE / "data/osm_food.json"
    if osm.exists():
        from food_safety.food_pois.models import PublicData as OSMData

        OSMData.model_validate_json(osm.read_text())
        if json.loads(osm.read_text()) != json.loads((ROOT / "data/osm_food.json").read_text()):
            present.append("public and approved OSM datasets differ")
    provider = SITE / "data/food_provider.json"
    if provider.exists():
        from food_safety.food_pois.models import PublicProvider

        PublicProvider.model_validate_json(provider.read_text())
        if json.loads(provider.read_text()) != json.loads(
            (ROOT / "data/food_provider.json").read_text()
        ):
            present.append("public and approved provider configuration differ")
    if places.exists():
        from food_safety.places.models import PublicData

        PublicData.model_validate_json(places.read_text())
        if json.loads(places.read_text()) != json.loads((ROOT / "data/places.json").read_text()):
            present.append("public and durable Places datasets differ")
    pandals = SITE / "data/pandals.json"
    if pandals.exists():
        from food_safety.puja.models import PublicData as PublicPandalData

        PublicPandalData.model_validate_json(pandals.read_text())
        if json.loads(pandals.read_text()) != json.loads((ROOT / "data/pandals.json").read_text()):
            present.append("public and durable pandal datasets differ")
    for path in SITE.rglob("*"):
        if path.is_symlink():
            present.append("symlink in public output")
        if any(
            part.startswith(".")
            or part
            in {
                "history",
                "pending",
                "rejected",
                "runs",
                "node_modules",
                "__pycache__",
                "llm_eval",
                "corpus",
                "places-runtime",
                "osm-runtime",
            }
            for part in path.relative_to(SITE).parts
        ):
            present.append("private path in public output")
        if not path.is_file():
            continue
        if any(value and value.encode() in path.read_bytes() for value in private_values):
            present.append("private value in public output")
        if path.parent == SITE / "data" and path.name not in allowed_data:
            present.append("unexpected public data file")
        if path.suffix not in {
            ".html",
            ".js",
            ".mjs",
            ".css",
            ".json",
            ".geojson",
            ".csv",
            ".svg",
            ".png",
            ".webp",
            ".md",
            ".txt",
        } and path.name not in {"_headers", "sitemap.xml"}:
            present.append("unexpected public asset type")
        if path.suffix not in {".png", ".webp"}:
            text = path.read_text()
            if path == SITE / "maps-config.json":
                if json.loads(text) != expected_maps:
                    present.append("unexpected browser Maps configuration")
                elif expected_maps["browser_key"]:
                    # Only the explicitly requested runtime artifact may carry this value.
                    text = text.replace(expected_maps["browser_key"], "BROWSER_KEY")
            if re.search(
                r"/Users/|BEGIN .*PRIVATE KEY|github_pat_[A-Za-z0-9_]{30,}"
                r"|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,}|AIza[A-Za-z0-9_-]{35}",
                text,
            ):
                present.append("private path or secret pattern")
    if missing or present or absent_headers:
        raise SystemExit(
            f"public-output gate failed: missing={missing}; forbidden={present}; "
            f"headers={absent_headers}"
        )
    print(f"Public output gate passed: {SITE}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true")
    parser.add_argument("--site", type=Path)
    args = parser.parse_args()
    if args.site:
        SITE = args.site.resolve()
    if args.runtime and SITE.resolve() == (ROOT / "site").resolve():
        raise SystemExit("Runtime validation requires a separate deployment directory")
    main(runtime=args.runtime)
