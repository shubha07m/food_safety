"""Fail-closed audit of the exact static directory eligible for publication."""

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
    "_headers",
]
FORBIDDEN = [".env", "data/pending.json", "data/rejected.json", "data/history", "data/runs"]


def main() -> None:
    validate(ROOT)
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
    }
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
            }
            for part in path.relative_to(SITE).parts
        ):
            present.append("private path in public output")
        if not path.is_file():
            continue
        if path.parent == SITE / "data" and path.name not in allowed_data:
            present.append("unexpected public data file")
        if (
            path.suffix
            not in {
                ".html",
                ".js",
                ".mjs",
                ".css",
                ".json",
                ".geojson",
                ".csv",
                ".svg",
                ".png",
                ".md",
                ".txt",
            }
            and path.name != "_headers"
        ):
            present.append("unexpected public asset type")
        if path.suffix != ".png":
            text = path.read_text()
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
    main()
