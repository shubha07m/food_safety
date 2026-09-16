"""One bounded Places API (New) operation; no Details, redirects, or consumer scraping."""

import json
import time
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import httpx

from .models import Observation

ENDPOINT = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = "places.id,places.displayName,places.location"
MAX_RESPONSE_BYTES = 131072
RETRYABLE = {429, 500, 502, 503, 504}


class PlacesError(Exception):
    """Only application-authored codes are exposed; never raw provider/request objects."""


def retry_delay(value):
    if not value:
        return 1.0
    try:
        delay = float(value)
    except ValueError:
        try:
            delay = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
        except (ValueError, TypeError, OverflowError):
            return None
    # Long Retry-After means defer to a later explicit run, not retry early.
    return max(0, delay) if 0 <= delay <= 5 else None


class Client:
    def __init__(self, key, settings, store, transport=None, sleep=time.sleep):
        if not key or not key.isascii() or any(c.isspace() or ord(c) < 33 for c in key):
            raise PlacesError("missing_or_invalid_google_maps_api_key")
        self._key = key
        self.settings = settings
        self.store = store
        self.transport = transport
        self.sleep = sleep

    def nearby(self, zone, max_results=None):
        if not zone.enabled or zone.radius_m > self.settings.max_zone_radius_m:
            raise PlacesError("disabled_or_oversized_zone")
        count = self.settings.max_results if max_results is None else max_results
        if not 1 <= count <= 20:
            raise PlacesError("invalid_result_limit")
        payload = {
            "includedTypes": ["restaurant"],
            "maxResultCount": count,
            "rankPreference": "DISTANCE",
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": zone.center_latitude,
                        "longitude": zone.center_longitude,
                    },
                    "radius": zone.radius_m,
                }
            },
        }
        with httpx.Client(
            timeout=self.settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
        ) as client:
            for attempt in range(self.settings.max_retries + 1):
                month = self.store.reserve(zone.zone_id)
                retry, delay = False, 1.0
                try:
                    with client.stream(
                        "POST",
                        ENDPOINT,
                        json=payload,
                        headers={
                            "X-Goog-Api-Key": self._key,
                            "X-Goog-FieldMask": FIELD_MASK,
                        },
                    ) as response:
                        if response.status_code != 200:
                            error = f"provider_http_{response.status_code}"
                            retry = response.status_code in RETRYABLE
                            delay = retry_delay(response.headers.get("Retry-After"))
                        else:
                            body = bytearray()
                            for chunk in response.iter_bytes(chunk_size=8192):
                                body.extend(chunk)
                                if len(body) > MAX_RESPONSE_BYTES:
                                    raise PlacesError("response_too_large")
                            at = self.store.clock()
                            if self._key.encode() in body:
                                raise PlacesError("provider_echoed_credential")
                            observations = self.parse(body, at, count)
                            self.store.outcome(zone.zone_id, month)
                            return observations, at
                except (httpx.TimeoutException, httpx.NetworkError):
                    error, retry = "provider_transport_error", True
                except httpx.HTTPError:
                    error = "provider_protocol_error"
                except PlacesError as exc:
                    error = str(exc)
                self.store.outcome(zone.zone_id, month, error)
                if not retry or delay is None or attempt == self.settings.max_retries:
                    raise PlacesError(error) from None
                self.sleep(delay)
        raise PlacesError("provider_unavailable")

    def parse(self, body, at, count):
        try:
            value = json.loads(body)
            if not isinstance(value, dict) or set(value) - {"places"}:
                raise ValueError("unexpected_envelope")
            places = value.get("places", [])
            if not isinstance(places, list) or len(places) > count:
                raise ValueError("invalid_results")
            observations = []
            for place in places:
                # displayName is deliberately discarded in memory, never persisted/logged.
                location = place["location"]
                observations.append(
                    Observation(
                        place_id=place["id"],
                        latitude=location["latitude"],
                        longitude=location["longitude"],
                        fetched_at=at,
                        expires_at=at + timedelta(days=self.settings.cache_days),
                    )
                )
            return observations
        except (ValueError, TypeError, KeyError):
            raise PlacesError("malformed_provider_response") from None
