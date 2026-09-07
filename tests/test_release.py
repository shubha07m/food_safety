from pathlib import Path

from food_safety.models import DerivedContext

ROOT = Path(__file__).resolve().parents[1]


def test_location_requires_reviewed_coarse_provenance():
    context = DerivedContext(
        latitude=22.55,
        longitude=88.35,
        location_precision="neighborhood",
        location_source="https://www.openstreetmap.org/",
        location_method="reviewed_openstreetmap_geocode",
        location_reviewed=True,
    )
    assert context.location_precision == "neighborhood"


def test_location_cannot_claim_precision_without_coordinate():
    try:
        DerivedContext(location_precision="city")
    except ValueError as exc:
        assert "unknown_location_must_not_claim_precision" in str(exc)
    else:
        raise AssertionError("location provenance without coordinates was accepted")


def test_release_gate_requires_explicit_confirmation_and_public_audit():
    script = (ROOT / "scripts/release_public_beta.sh").read_text(encoding="utf-8")
    audit = (ROOT / "scripts/verify_public_output.py").read_text(encoding="utf-8")
    assert "--confirm-public-release" in script
    assert "git status --porcelain" in script
    assert "verify_public_output.py" in script
    assert "data/pending.json" in audit
    assert "data/history" in audit
