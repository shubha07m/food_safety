"""OSM data is durable and ODbL; Google data stays in the existing separate contract."""

import unicodedata
from collections import Counter
from typing import Literal
from urllib.parse import urlencode

from pydantic import AwareDatetime, Field, HttpUrl, model_validator

from ..places.models import ID, Latitude, Longitude, PlaceID, Strict

ATTRIBUTION = "© OpenStreetMap contributors"
COPYRIGHT = "https://www.openstreetmap.org/copyright"
LICENSE = "https://opendatacommons.org/licenses/odbl/1-0/"
FOOD_TAGS = {
    "amenity": {"restaurant", "cafe", "fast_food", "ice_cream", "food_court"},
    "shop": {"bakery", "confectionery"},
}


def normalize(value):
    return " ".join(unicodedata.normalize("NFC", value or "").casefold().split())


class Bounds(Strict):
    west: Longitude
    south: Latitude
    east: Longitude
    north: Latitude

    @model_validator(mode="after")
    def ordered(self):
        if not self.west < self.east or not self.south < self.north:
            raise ValueError("invalid_region")
        if self.east - self.west > 5 or self.north - self.south > 5:
            raise ValueError("research_region_too_large")
        return self

    def contains(self, lat, lon):
        return self.south <= lat <= self.north and self.west <= lon <= self.east


class OSMConfig(Strict):
    enabled: bool = True
    source_url: HttpUrl
    source_path: str
    dataset: str
    max_download_bytes: int = Field(default=400_000_000, ge=1, le=2_000_000_000)
    bbox: Bounds
    bbox_basis: str
    catchment_radius_m: float | None = Field(default=None, ge=600, le=5000)
    categories: dict[Literal["amenity", "shop"], list[str]]

    @model_validator(mode="after")
    def food_categories(self):
        if not any(self.categories.values()) or any(
            set(values) - FOOD_TAGS[key] or len(set(values)) != len(values)
            for key, values in self.categories.items()
        ):
            raise ValueError("invalid_food_categories")
        return self


class VerifiedLink(Strict):
    poi_id: str = Field(pattern=r"^osm:(node|way|relation):[1-9][0-9]*$")
    place_id: PlaceID
    identity_source: HttpUrl
    verified_at: AwareDatetime
    note: str = Field(min_length=20, max_length=1000)


class Enrichment(Strict):
    enabled: bool = False
    pandal_ids: list[ID] = Field(default_factory=list)
    max_unique_pois: int = Field(default=10, ge=1, le=30)
    verified_links: list[VerifiedLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique(self):
        for values in (
            [x.poi_id for x in self.verified_links],
            [x.place_id for x in self.verified_links],
        ):
            if len(set(values)) != len(values):
                raise ValueError("ambiguous_crosswalk")
        return self


class Config(Strict):
    provider: Literal["osm", "google", "hybrid"] = "google"
    initial_display_limit: int = Field(default=12, ge=10, le=15)
    osm: OSMConfig
    google_enrichment: Enrichment = Field(default_factory=Enrichment)


class FoodPOI(Strict):
    """Provider-neutral spatial identity; Google instances are runtime-only."""

    poi_id: str
    provider: Literal["osm", "google"]
    provider_id: str
    name: str | None = Field(default=None, min_length=1, max_length=500)
    latitude: Latitude
    longitude: Longitude

    @model_validator(mode="after")
    def qualified_identity(self):
        expected = f"{self.provider}:{self.provider_id.replace('/', ':')}"
        if self.poi_id != expected:
            raise ValueError("provider_identity_mismatch")
        return self


class OSMFoodPOI(FoodPOI):
    """Durable OSM specialization; never accepts Google coordinate content."""

    provider: Literal["osm"] = "osm"
    osm_type: Literal["node", "way", "relation"]
    osm_id: int = Field(gt=0)
    name_bn: str | None = Field(default=None, min_length=1, max_length=500)
    category: str
    amenity: str | None = None
    shop: str | None = None
    cuisine: str | None = Field(default=None, max_length=500)
    brand: str | None = Field(default=None, max_length=500)
    operator: str | None = Field(default=None, max_length=500)
    opening_hours: str | None = Field(default=None, max_length=1000)
    coordinate_method: Literal["osm_node", "polygon_interior", "way_midpoint"]
    source_url: HttpUrl
    source_timestamp: AwareDatetime | None = None
    merged_osm_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def identity(self):
        if self.poi_id != f"osm:{self.osm_type}:{self.osm_id}":
            raise ValueError("invalid_osm_identity")
        if self.provider_id != f"{self.osm_type}/{self.osm_id}":
            raise ValueError("invalid_provider_identity")
        if str(self.source_url) != f"https://www.openstreetmap.org/{self.provider_id}":
            raise ValueError("invalid_osm_source")
        if not any(
            self.category == getattr(self, key) and self.category in allowed
            for key, allowed in FOOD_TAGS.items()
        ):
            raise ValueError("unsupported_category")
        return self

    def maps_url(self, place_id=None):
        query = f"{self.name or self.category} {self.latitude:.7f},{self.longitude:.7f}"
        params = {"api": "1", "query": query}
        if place_id is not None:
            from pydantic import TypeAdapter

            params["query_place_id"] = TypeAdapter(PlaceID).validate_python(place_id)
        return "https://www.google.com/maps/search/?" + urlencode(params)


class Association(Strict):
    pandal_id: ID
    poi_id: str
    provider: Literal["osm"] = "osm"
    distance_m: float = Field(ge=0, allow_inf_nan=False)
    source_snapshot: str


class CoverageCircle(Strict):
    latitude: Latitude
    longitude: Longitude
    radius_m: float = Field(gt=0, le=5000, allow_inf_nan=False)


class Snapshot(Strict):
    schema_version: Literal["food-osm-1"] = "food-osm-1"
    snapshot_id: str
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_dataset: str
    source_url: HttpUrl
    snapshot_date: AwareDatetime | None = None
    extracted_at: AwareDatetime
    bbox: Bounds
    # Absent for whole-bbox extracts; explicit for bounded venue subsets.
    coverage_circles: list[CoverageCircle] | None = Field(default=None, min_length=1)
    attribution: Literal["© OpenStreetMap contributors"] = ATTRIBUTION
    attribution_url: Literal["https://www.openstreetmap.org/copyright"] = COPYRIGHT
    license: Literal["ODbL-1.0"] = "ODbL-1.0"
    license_url: Literal["https://opendatacommons.org/licenses/odbl/1-0/"] = LICENSE
    normalization_version: Literal[1] = 1
    diagnostics: dict[str, int] = Field(default_factory=dict)
    pois: list[OSMFoodPOI]

    @model_validator(mode="after")
    def unique(self):
        if len({p.poi_id for p in self.pois}) != len(self.pois):
            raise ValueError("duplicate_poi_id")
        if any(not self.bbox.contains(p.latitude, p.longitude) for p in self.pois):
            raise ValueError("poi_outside_snapshot_region")
        return self


class Coverage(Strict):
    pandal_id: ID
    status: Literal["snapshot", "outside_region"]
    radius_m: float = Field(gt=0, le=50000)
    association_count: int = Field(ge=0)


class PublicData(Snapshot):
    associations: list[Association] = Field(default_factory=list)
    coverage: list[Coverage] = Field(default_factory=list)

    @model_validator(mode="after")
    def links(self):
        ids = {p.poi_id for p in self.pois}
        covered = {c.pandal_id for c in self.coverage if c.status == "snapshot"}
        counts = Counter(a.pandal_id for a in self.associations)
        coverage = {c.pandal_id: c for c in self.coverage}
        if len(coverage) != len(self.coverage) or any(
            counts[c.pandal_id] != c.association_count for c in self.coverage
        ):
            raise ValueError("invalid_coverage_count")
        keys = [(a.pandal_id, a.poi_id) for a in self.associations]
        if len(set(keys)) != len(keys) or any(
            a.poi_id not in ids
            or a.pandal_id not in covered
            or a.source_snapshot != self.snapshot_id
            or a.distance_m > coverage[a.pandal_id].radius_m
            for a in self.associations
        ):
            raise ValueError("invalid_association")
        return self


class PublicProvider(Strict):
    schema_version: Literal["food-provider-1"] = "food-provider-1"
    provider: Literal["osm", "google", "hybrid"]
    initial_display_limit: int = Field(ge=10, le=15)
    google_links: list[VerifiedLink] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_links(self):
        Enrichment(verified_links=self.google_links)
        return self
