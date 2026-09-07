"""Fail-closed audit of the exact static directory eligible for publication."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REQUIRED = [
    "index.html", "disclaimer.html", "methodology.html", "corrections.html", "data.html",
    "data/events.json", "data/events.csv", "data/events.csv.metadata.json", "_headers",
]
FORBIDDEN = [".env", "data/pending.json", "data/rejected.json", "data/history", "data/runs"]


def main() -> None:
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
    dataset = (SITE / "data/events.json").read_text(encoding="utf-8")
    if "PENDING REVIEW" in dataset or '"is_fixture": true' in dataset:
        present.append("non-public record marker in events.json")
    if missing or present or absent_headers:
        raise SystemExit(
            f"public-output gate failed: missing={missing}; forbidden={present}; "
            f"headers={absent_headers}"
        )
    print(f"Public output gate passed: {SITE}")


if __name__ == "__main__":
    main()
