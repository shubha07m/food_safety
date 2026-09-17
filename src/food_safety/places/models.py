"""Separate durable curated data from short-lived Google coordinate observations."""

from datetime import timedelta
from typing import Annotated, Literal
from urllib.parse import urlencode

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

ID = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")]
PlaceID = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{1,255}$")]
Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Pandal(Strict):
    pandal_id: ID
    name: str = Field(min_length=1, max_length=200)
    name_bn: str | None = Field(default=None, max_length=200)
    area: str = Field(min_length=1, max_length=200)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    restaurant_radius_m: float = Field(default=500, gt=0, le=1500)
    enabled: bool = False
    coordinate_source: HttpUrl | None = None
    notes: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def coordinates(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("coordinate_pair_required")
        if self.enabled and (self.latitude is None or not self.coordinate_source):
            raise ValueError("enabled_pandal_requires_sourced_coordinates")
        if self.coordinate_source and any(
            s in self.coordinate_source.host.lower() for s in ("google", "goo.gl", "gstatic")
        ):
            raise ValueError("pandal_anchor_requires_non_google_provenance")
        return self


class Zone(Strict):
    zone_id: ID
    name: str = Field(min_length=1, max_length=200)
    center_latitude: Latitude
    center_longitude: Longitude
    radius_m: float = Field(gt=0, le=50000)
    pandal_ids: list[ID] = Field(min_length=1, max_length=50)
    enabled: bool = True


class Settings(Strict):
    monthly_limit: int = Field(default=3000, ge=1, le=3000)
    warning_threshold: int = Field(default=2500, ge=0, le=3000)
    max_calls_per_run: int = Field(default=60, ge=1, le=60)
    max_results: int = Field(default=10, ge=1, le=20)
    max_retries: int = Field(default=1, ge=0, le=2)
    timeout_seconds: int = Field(default=15, ge=1, le=30)
    cache_days: int = Field(default=7, ge=1, le=30)
    max_zone_radius_m: int = Field(default=1500, ge=1, le=50000)
    overlap_fraction: float = Field(default=0.7, gt=0, lt=1)
    automatic_zones: bool = True
    default_restaurant_radius_m: int = Field(default=600, ge=300, le=1500)
    max_supplemental_searches: int = Field(default=3, ge=0, le=3)
    supplemental_offset_m: int = Field(default=300, ge=100, le=500)
    supplemental_radius_m: int = Field(default=400, ge=200, le=600)

    @model_validator(mode="after")
    def limits(self):
        if self.warning_threshold > self.monthly_limit:
            raise ValueError("warning_exceeds_limit")
        return self


class CuratedRestaurant(Strict):
    place_id: PlaceID
    name: str = Field(min_length=1, max_length=200)
    independent_source: HttpUrl
    source_kind: Literal["independently_curated"] = "independently_curated"

    @model_validator(mode="after")
    def independent(self):
        host = self.independent_source.host.lower()
        if any(s in host for s in ("google", "goo.gl", "gstatic")):
            raise ValueError("google_is_not_an_independent_name_source")
        return self


class Config(Strict):
    settings: Settings = Field(default_factory=Settings)
    pandals: list[Pandal] = Field(default_factory=list, max_length=300)
    zones: list[Zone] = Field(default_factory=list, max_length=300)
    restaurants: list[CuratedRestaurant] = Field(default_factory=list, max_length=10000)

    @model_validator(mode="after")
    def references(self):
        for items in (
            [p.pandal_id for p in self.pandals],
            [z.zone_id for z in self.zones],
            [r.place_id for r in self.restaurants],
        ):
            if len(items) != len(set(items)):
                raise ValueError("duplicate_id")
        known = {p.pandal_id for p in self.pandals}
        assigned = set()
        for z in self.zones:
            if len(z.pandal_ids) != len(set(z.pandal_ids)):
                raise ValueError("duplicate_zone_member")
            if set(z.pandal_ids) - known:
                raise ValueError("unknown_pandal")
            if assigned.intersection(z.pandal_ids):
                raise ValueError("pandal_in_multiple_search_zones")
            assigned.update(z.pandal_ids)
            if z.radius_m > self.settings.max_zone_radius_m:
                raise ValueError("zone_exceeds_practical_radius_limit")
        return self


class Observation(Strict):
    place_id: PlaceID
    latitude: Latitude
    longitude: Longitude
    source: Literal["google_places"] = "google_places"
    fetched_at: AwareDatetime
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def retention(self):
        if not timedelta(0) < self.expires_at - self.fetched_at <= timedelta(days=30):
            raise ValueError("invalid_coordinate_retention")
        return self


class Snapshot(Strict):
    query_hash: str
    fetched_at: AwareDatetime
    expires_at: AwareDatetime
    observations: list[Observation] = Field(max_length=20)
    result_limit_reached: bool

    @model_validator(mode="after")
    def retention(self):
        if not timedelta(0) < self.expires_at - self.fetched_at <= timedelta(days=30):
            raise ValueError("invalid_snapshot_retention")
        if any(
            o.fetched_at != self.fetched_at or o.expires_at != self.expires_at
            for o in self.observations
        ):
            raise ValueError("observation_snapshot_time_mismatch")
        return self


class Restaurant(Strict):
    place_id: PlaceID
    source: Literal["google_places_id"] = "google_places_id"
    curated: CuratedRestaurant | None = None


class Association(Strict):
    pandal_id: ID
    place_id: PlaceID
    observed_at: AwareDatetime
    provenance: Literal["google_places_local_radius_match"] = "google_places_local_radius_match"


class Discovery(Strict):
    pandal_id: ID
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    candidates_returned: int = Field(ge=0, le=80)
    result_limit_reached: bool
    primary_result_count: int = Field(default=0, ge=0, le=20)
    supplemental_search_count: int = Field(default=0, ge=0, le=3)
    raw_candidate_count: int = Field(default=0, ge=0, le=80)
    candidate_unique_count: int = Field(default=0, ge=0, le=80)
    association_count: int = Field(default=0, ge=0, le=10000)
    saturation_encountered: bool = False
    overlap_ratio: float = Field(default=0, ge=0, le=1)
    calls_used: int = Field(default=0, ge=0, le=60)
    last_enriched_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def dates(self):
        if not timedelta(0) < self.expires_at - self.observed_at <= timedelta(days=30):
            raise ValueError("invalid_discovery_window")
        return self


class SearchDiagnostic(Strict):
    zone_id: ID
    observed_at: AwareDatetime
    expires_at: AwareDatetime
    result_count: int = Field(ge=0, le=20)
    saturated: bool
    supplemental_search_count: int = Field(ge=0, le=3)
    raw_candidate_count: int = Field(ge=0, le=80)
    unique_place_count_after_dedupe: int = Field(ge=0, le=80)
    associations_created: int = Field(ge=0, le=10000)
    overlap_ratio: float = Field(ge=0, le=1)
    calls_used: int = Field(ge=0, le=60)

    @model_validator(mode="after")
    def dates(self):
        if not timedelta(0) < self.expires_at - self.observed_at <= timedelta(days=30):
            raise ValueError("invalid_diagnostic_window")
        return self


class Registry(Strict):
    restaurants: list[Restaurant] = Field(default_factory=list)
    associations: list[Association] = Field(default_factory=list)
    discoveries: list[Discovery] = Field(default_factory=list)
    search_diagnostics: list[SearchDiagnostic] = Field(default_factory=list)


class PublicRestaurant(Restaurant):
    google_maps_url: str

    @model_validator(mode="after")
    def link(self):
        if self.google_maps_url != maps_url(self.place_id):
            raise ValueError("incorrect_maps_handoff")
        return self


class PublicData(Strict):
    schema_version: Literal["places-1"] = "places-1"
    association_semantics: Literal["historical_discovery_not_current_proximity"] = (
        "historical_discovery_not_current_proximity"
    )
    attribution: Literal["Google Maps"] = "Google Maps"
    pandals: list[Pandal]
    zones: list[Zone]
    restaurants: list[PublicRestaurant]
    associations: list[Association]
    discoveries: list[Discovery] = Field(default_factory=list)
    search_diagnostics: list[SearchDiagnostic] = Field(default_factory=list)

    @model_validator(mode="after")
    def references(self):
        pandals = {p.pandal_id for p in self.pandals}
        places = {r.place_id for r in self.restaurants}
        if len(pandals) != len(self.pandals) or len(places) != len(self.restaurants):
            raise ValueError("duplicate_public_id")
        if any(a.pandal_id not in pandals or a.place_id not in places for a in self.associations):
            raise ValueError("invalid_public_association")
        if len({d.pandal_id for d in self.discoveries}) != len(self.discoveries) or any(
            d.pandal_id not in pandals for d in self.discoveries
        ):
            raise ValueError("invalid_public_discovery")
        zone_ids = {z.zone_id for z in self.zones}
        if len({d.zone_id for d in self.search_diagnostics}) != len(
            self.search_diagnostics
        ) or any(d.zone_id not in zone_ids for d in self.search_diagnostics):
            raise ValueError("invalid_search_diagnostics")
        return self


def maps_url(place_id: str) -> str:
    # Both query and query_place_id are required for a reliable Maps URL handoff.
    from pydantic import TypeAdapter

    place_id = TypeAdapter(PlaceID).validate_python(place_id)
    return "https://www.google.com/maps/search/?" + urlencode(
        {"api": "1", "query": "restaurant", "query_place_id": place_id}
    )
