"""Import maintainer-approved Google Form CSV rows into the ignored local lead queue."""

import argparse
from pathlib import Path

from food_safety.community import import_approved_csv
from food_safety.config import ROOT, sources


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    source = args.csv.resolve()
    if not source.is_relative_to(ROOT):
        raise SystemExit("CSV must be inside the project directory")
    count = import_approved_csv(
        source, ROOT / "data/tmp/community_leads.json", sources(ROOT)
    )
    print(f"Imported {count} approved public-source leads; no submitter data retained.")


if __name__ == "__main__":
    main()
