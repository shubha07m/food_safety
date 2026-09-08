"""Extract only West Bengal from the pinned geoBoundaries simplified ADM1 file.

Input is a manually downloaded, size-capped development asset, never a runtime fetch.
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / ".cache/india-adm1.geojson").read_text())
    features = [f for f in data["features"] if f["properties"]["shapeName"] == "West Bengal"]
    if len(features) != 1:
        raise ValueError("Expected exactly one West Bengal feature")
    feature = features[0]
    # Retain original simplified coordinates; no invented boundary geometry.
    feature["properties"] = {
        "name": "West Bengal",
        "source": "geoBoundaries gbOpen IND ADM1",
        "license": "CC BY 2.5 IN",
        "revision": "9469f09",
    }
    destination = ROOT / "site/assets/west-bengal.geojson"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(feature, separators=(",", ":")) + "\n")
    print(f"West Bengal boundary: {destination.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
