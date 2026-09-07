import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

ROOT = Path(__file__).resolve().parents[1]


def _locked_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in (ROOT / "requirements-dev.lock").read_text(encoding="utf-8").splitlines():
        value = line.strip()
        if not value or value.startswith("#"):
            continue
        requirement = Requirement(value)
        pinned = [item.version for item in requirement.specifier if item.operator == "=="]
        assert len(pinned) == 1, f"lock entry is not an exact pin: {value}"
        versions[canonicalize_name(requirement.name)] = pinned[0]
    return versions


def test_direct_dependency_pins_match_resolved_lock() -> None:
    document = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    declared = [
        *document["build-system"]["requires"],
        *document["project"]["dependencies"],
        *document["project"]["optional-dependencies"]["dev"],
    ]
    locked = _locked_versions()

    for value in declared:
        requirement = Requirement(value)
        pinned = [item.version for item in requirement.specifier if item.operator == "=="]
        assert len(pinned) == 1, f"direct dependency is not an exact pin: {value}"
        name = canonicalize_name(requirement.name)
        assert name in locked, f"direct dependency missing from lock: {requirement.name}"
        assert locked[name] == pinned[0], (
            f"lock mismatch for {requirement.name}: declared {pinned[0]}, "
            f"locked {locked[name]}"
        )
