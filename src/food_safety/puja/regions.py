"""Puja-only region registry; evidence geography is not derived from this registry."""

import json
from typing import Literal
from urllib.parse import urlencode

import yaml
from pydantic import Field, model_validator

from ..places.models import ID, Latitude, Longitude, Strict


class Center(Strict):
    lat: Latitude
    lng: Longitude


class RegionalFoodSearch(Strict):
    type: Literal["regional_food_search"] = "regional_food_search"
    area_id: ID
    label: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=200)
    provider: Literal["Google Maps"] = "Google Maps"
    scope_note: str = "Regional search handoff, not a verified restaurant record"


class Region(Strict):
    region_id: ID
    label: str
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    admin1: str | None = None
    timezone: str | None = None
    default_map_center: Center
    default_map_zoom: int = Field(ge=1, le=16)
    safety_context: bool = False
    geocode_bounds: tuple[Longitude, Latitude, Longitude, Latitude]
    food_config: str = Field(pattern=r"^config/[a-z0-9_-]+\.yml$")
    food_data: str = Field(pattern=r"^data/[a-z0-9_-]+\.json$")
    provider_data: str = Field(pattern=r"^data/[a-z0-9_-]+\.json$")
    catalog_config: str | None = Field(default=None, pattern=r"^config/[a-z0-9_-]+\.yml$")
    featured_ids: list[ID] = Field(default_factory=list)
    restaurant_radius_m: float = Field(default=600, ge=100, le=5000)
    regional_food_searches: list[RegionalFoodSearch] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def bounds(self):
        w, s, e, n = self.geocode_bounds
        if w >= e or s >= n:
            raise ValueError("invalid_region_bounds")
        ids = [s.area_id for s in self.regional_food_searches]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate_regional_food_search")
        return self


class Regions(Strict):
    default_region: ID
    regions: list[Region] = Field(min_length=1)

    @model_validator(mode="after")
    def unique(self):
        ids = [r.region_id for r in self.regions]
        if len(set(ids)) != len(ids) or self.default_region not in ids:
            raise ValueError("invalid_region_registry")
        return self


def load_regions(root):
    return Regions.model_validate(yaml.safe_load((root / "config/regions.yml").read_text()))


def get_region(root, region_id):
    for region in load_regions(root).regions:
        if region.region_id == region_id:
            return region
    raise ValueError("unknown_region")


def public_registry(root):
    from ..food_pois.osm import load_config

    config = load_regions(root)
    value = {
        "schema_version": "puja-regions-1",
        "default_region": config.default_region,
        "regions": [],
    }
    for region in config.regions:
        item = region.model_dump(exclude={"catalog_config", "geocode_bounds", "food_config"})
        item["food_provider_mode"] = load_config(root, region.region_id).provider
        item["regional_food_searches"] = [
            {
                **s.model_dump(),
                "region_id": region.region_id,
                "maps_url": "https://www.google.com/maps/search/?"
                + urlencode({"api": "1", "query": s.query}),
            }
            for s in region.regional_food_searches
        ]
        value["regions"].append(item)
    return value


def build_regions(root):
    from ..places.storage import write_json

    value = public_registry(root)
    # No account configuration or runtime/provider observations in this contract.
    for path in (root / "data/regions.json", root / "site/data/regions.json"):
        write_json(path, value)
    return json.loads(json.dumps(value))
