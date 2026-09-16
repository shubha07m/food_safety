"""Ignored operational ledger, exclusive process lock, atomic durable writes."""

import fcntl
import json
import os
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime

from pydantic import AwareDatetime, Field, model_validator

from .models import ID, Strict


def utcnow():
    return datetime.now(UTC)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False) as stream:
        temporary = stream.name
        try:
            json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            os.unlink(temporary)
            raise
    try:
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class ZoneUsage(Strict):
    calls: int = Field(default=0, ge=0)
    last_attempt_at: AwareDatetime | None = None
    last_fetch_at: AwareDatetime | None = None
    last_error: str | None = None


class MonthUsage(Strict):
    calls: int = Field(default=0, ge=0)
    zones: dict[ID, ZoneUsage] = Field(default_factory=dict)

    @model_validator(mode="after")
    def totals(self):
        if self.calls != sum(z.calls for z in self.zones.values()):
            raise ValueError("ledger_totals_disagree")
        return self


class Ledger(Strict):
    version: int = Field(default=1, ge=1, le=1)
    months: dict[str, MonthUsage] = Field(default_factory=dict)
    last_attempt_at: AwareDatetime | None = None


class LimitReached(Exception):
    pass


class Store:
    def __init__(self, root, settings, max_calls=None, clock=utcnow):
        self.root = root
        self.directory = root / "data/places-runtime"
        self.settings = settings
        if max_calls is not None and not 1 <= max_calls <= settings.max_calls_per_run:
            raise ValueError("invalid_run_limit")
        self.max_calls = max_calls or settings.max_calls_per_run
        self.calls = 0
        self.clock = clock

    def read_ledger(self):
        path = self.directory / "usage.json"
        if path.exists():
            return Ledger.model_validate_json(path.read_text())
        if (self.directory / "initialized").exists() or (
            self.directory / "observations.json"
        ).exists():
            raise ValueError("missing_usage_ledger_restore_before_discovery")
        return Ledger()

    @contextmanager
    def lock(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        with (self.directory / "lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                self.ledger = self.read_ledger()
                yield self
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def reserve(self, zone_id):
        at = self.clock()
        if self.ledger.last_attempt_at and at < self.ledger.last_attempt_at:
            raise LimitReached("clock_moved_backwards")
        month = self.ledger.months.setdefault(at.strftime("%Y-%m"), MonthUsage())
        if month.calls >= self.settings.monthly_limit:
            raise LimitReached("monthly_limit")
        if self.calls >= self.max_calls:
            raise LimitReached("run_limit")
        zone = month.zones.setdefault(zone_id, ZoneUsage())
        zone.calls += 1
        zone.last_attempt_at = at
        month.calls += 1
        self.calls += 1
        self.ledger.last_attempt_at = at
        # Reserve before send: a crash can overcount, never undercount.
        self.save()
        (self.directory / "initialized").touch(mode=0o600)
        return at.strftime("%Y-%m")

    def outcome(self, zone_id, month, error=None):
        zone = self.ledger.months[month].zones[zone_id]
        zone.last_error = error
        if error is None:
            zone.last_fetch_at = self.clock()
        self.save()

    def save(self):
        write_json(self.directory / "usage.json", self.ledger.model_dump(mode="json"))

    def status(self):
        ledger = self.read_ledger()
        month_id = self.clock().strftime("%Y-%m")
        month = ledger.months.get(month_id, MonthUsage())
        return {
            "month_utc": month_id,
            **month.model_dump(mode="json"),
            "monthly_limit": self.settings.monthly_limit,
            "warning_threshold": self.settings.warning_threshold,
            "warning": month.calls >= self.settings.warning_threshold,
            "remaining": max(0, self.settings.monthly_limit - month.calls),
            "max_calls_per_run": self.max_calls,
        }
