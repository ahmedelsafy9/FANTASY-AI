"""Shared authoritative gameweek context for Fantasy-AI.

All player predictions, match predictions, captain recommendations,
squad building, chatbot answers, and feedback processing must resolve
gameweeks through this module rather than inferring completion from a
single finished fixture or a lower numeric identifier.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import Settings

logger = get_logger(__name__)


def infer_fpl_season(now: datetime | None = None) -> str:
    """Infer the FPL season label from a UTC timestamp.

    The Premier League / FPL season is treated as starting in August.

    Args:
        now: Timestamp to infer from. Defaults to UTC now.

    Returns:
        Season label such as ``2026-27``.
    """
    moment = now or datetime.now(timezone.utc)
    year = moment.year
    if moment.month >= 8:
        return f"{year}-{str(year + 1)[2:]}"
    return f"{year - 1}-{str(year)[2:]}"


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass(frozen=True)
class GameweekContext:
    """Authoritative gameweek state shared across prediction services.

    Attributes:
        season: Current FPL season string (e.g. ``2026-27``).
        latest_completed_gameweek: Highest gameweek whose official status
            is finished (all fixtures complete). ``0`` before GW1 finishes.
        target_gameweek: Gameweek being predicted (next upcoming unless
            an explicit historical gameweek was requested).
        is_gameweek_active: True when the official current event is not finished.
        next_deadline: ISO timestamp of the target gameweek deadline.
        is_synchronized: True when player and match models share this context.
        source: Resolver source (``fpl_bootstrap``, ``fpl_fixtures``,
            ``engineered_data``, ``default``).
        status: ``synchronized``, ``partial``, ``transition``, ``fallback``,
            ``historical``, or ``degraded``.
        current_gameweek: Official ``is_current`` event id, if any.
        next_upcoming_gameweek: Official ``is_next`` event, otherwise derived.
        requested_gameweek: Explicit historical/override gameweek, if any.
        prediction_cutoff: Timestamp after which target-GW outcomes must
            not be used as features (usually the target deadline).
        fixture_ids: Fixture identifiers belonging to the target gameweek.
        freshness_status: ``fresh``, ``stale``, ``degraded``, or ``unknown``.
        data_timestamp: When the source payload was read.
        completeness: ``complete``, ``partial``, ``postponed``, ``unknown``.
        degraded: True when resolution used a fallback or incomplete source.
    """

    season: str
    latest_completed_gameweek: int
    target_gameweek: int
    is_gameweek_active: bool
    next_deadline: str | None
    is_synchronized: bool
    source: str
    status: str
    current_gameweek: int | None = None
    next_upcoming_gameweek: int | None = None
    requested_gameweek: int | None = None
    prediction_cutoff: str | None = None
    fixture_ids: tuple[int, ...] = field(default_factory=tuple)
    freshness_status: str = "unknown"
    data_timestamp: str | None = None
    completeness: str = "unknown"
    degraded: bool = False

    @property
    def last_completed_gameweek(self) -> int:
        """Alias used by the product contract."""
        return self.latest_completed_gameweek

    def to_public_dict(self) -> dict[str, Any]:
        """Serialize fields safe to expose through APIs and tools."""
        return {
            "season": self.season,
            "last_completed_gameweek": self.last_completed_gameweek,
            "latest_completed_gameweek": self.latest_completed_gameweek,
            "current_gameweek": self.current_gameweek,
            "next_upcoming_gameweek": self.next_upcoming_gameweek,
            "target_gameweek": self.target_gameweek,
            "requested_gameweek": self.requested_gameweek,
            "prediction_cutoff": self.prediction_cutoff,
            "is_gameweek_active": self.is_gameweek_active,
            "next_deadline": self.next_deadline,
            "fixture_ids": list(self.fixture_ids),
            "freshness_status": self.freshness_status,
            "data_timestamp": self.data_timestamp,
            "completeness": self.completeness,
            "degraded": self.degraded,
            "source": self.source,
            "status": self.status,
            "is_synchronized": self.is_synchronized,
        }


def _completed_from_events(events: list[dict[str, Any]]) -> int:
    completed = [
        int(event["id"])
        for event in events
        if event.get("finished") and event.get("id") is not None
    ]
    return max(completed) if completed else 0


def _fixture_completeness(
    fixtures: list[dict[str, Any]],
    gameweek: int,
) -> tuple[str, tuple[int, ...]]:
    """Classify a gameweek from fixture rows.

    A gameweek is complete only when it has at least one assigned fixture
    and every assigned fixture is finished. A single finished match is
    not sufficient.
    """
    assigned = [f for f in fixtures if f.get("event") == gameweek]
    ids = tuple(int(f["id"]) for f in assigned if f.get("id") is not None)
    if not assigned:
        unassigned = [
            f
            for f in fixtures
            if f.get("event") is None
            and not f.get("finished", False)
        ]
        if unassigned:
            return "postponed", ids
        return "unknown", ids

    finished_flags = [bool(f.get("finished", False)) for f in assigned]
    if all(finished_flags):
        return "complete", ids
    if any(finished_flags):
        return "partial", ids
    return "unknown", ids


def resolve_authoritative_gameweek(
    settings: Settings,
    bootstrap_data: dict[str, Any] | None = None,
    fixtures_data: list[dict[str, Any]] | None = None,
    engineered_data: pd.DataFrame | None = None,
    current_time: datetime | None = None,
    requested_gameweek: int | None = None,
) -> GameweekContext:
    """Resolve the authoritative gameweek for the next prediction round.

    Priority:
    1. FPL bootstrap-static events (official deadlines and finished flags).
    2. FPL fixtures (complete vs partial vs postponed).
    3. Engineered historical dataset (fallback).

    Live prediction target is the next upcoming gameweek, not an
    in-progress round, unless an explicit historical gameweek is requested.

    Args:
        settings: Application settings.
        bootstrap_data: Optional pre-loaded bootstrap-static dict.
        fixtures_data: Optional pre-loaded fixtures list.
        engineered_data: Optional historical engineered DataFrame.
        current_time: Optional datetime override (defaults to UTC now).
        requested_gameweek: Explicit historical or override gameweek.

    Returns:
        GameweekContext shared by every prediction consumer.
    """
    now = current_time or datetime.now(timezone.utc)
    configured_season = getattr(settings.automation, "current_season", "") or ""
    season = configured_season.strip() or infer_fpl_season(now)
    max_gw = getattr(settings.prediction, "max_valid_gameweek", 38)
    explicit = requested_gameweek
    if explicit is None:
        configured = getattr(settings.prediction, "target_gameweek", None)
        if configured is not None:
            explicit = int(configured)

    bootstrap = bootstrap_data
    bootstrap_path: Path | None = None
    if bootstrap is None:
        live_dir = settings.paths.raw_data_dir / "fpl_api"
        bootstrap_path = live_dir / "bootstrap_static.json"
        if bootstrap_path.exists():
            try:
                bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Could not read bootstrap_static.json: %s", exc)
                bootstrap_path = None
        else:
            bootstrap_path = None

    fixtures = fixtures_data
    fixtures_path: Path | None = None
    if fixtures is None:
        fixtures_path = settings.paths.raw_data_dir / "fpl_api" / "fixtures.json"
        if fixtures_path.exists():
            try:
                fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Could not read fixtures.json: %s", exc)
                fixtures = None
        else:
            fixtures = None

    data_timestamp = now.isoformat()
    if bootstrap_path and bootstrap_path.exists():
        data_timestamp = datetime.fromtimestamp(
            bootstrap_path.stat().st_mtime, tz=timezone.utc
        ).isoformat()

    if bootstrap and "events" in bootstrap and bootstrap["events"]:
        events = bootstrap["events"]
        latest_completed = min(_completed_from_events(events), max_gw)
        current_event = next((e for e in events if e.get("is_current")), None)
        next_event = next((e for e in events if e.get("is_next")), None)
        current_gw = int(current_event["id"]) if current_event and current_event.get("id") else None
        is_active = bool(current_event is not None and not current_event.get("finished", False))

        if next_event is not None and next_event.get("id") is not None:
            next_upcoming = int(next_event["id"])
        elif is_active and current_gw is not None:
            next_upcoming = min(current_gw + 1, max_gw)
        elif latest_completed > 0:
            next_upcoming = min(latest_completed + 1, max_gw)
        else:
            next_upcoming = 1

        if explicit is not None:
            target_gw = min(max(1, int(explicit)), max_gw)
            status = "historical"
        else:
            target_gw = min(max(1, next_upcoming), max_gw)
            status = "synchronized"

        ev_target = next((e for e in events if e.get("id") == target_gw), None)
        deadline = ev_target.get("deadline_time") if ev_target else None
        if deadline is None and next_event is not None:
            deadline = next_event.get("deadline_time")

        completeness = "unknown"
        fixture_ids: tuple[int, ...] = ()
        if fixtures:
            completeness, fixture_ids = _fixture_completeness(fixtures, target_gw)
            if completeness == "partial" and status == "synchronized":
                status = "partial"
            elif completeness == "postponed" and status == "synchronized":
                status = "partial"

        freshness = "fresh"
        source_age = _parse_iso(data_timestamp)
        if source_age and (now - source_age).total_seconds() > 36 * 3600:
            freshness = "stale"

        logger.info(
            "GameweekContext from bootstrap: completed=%d current=%s next=%d target=%d active=%s",
            latest_completed,
            current_gw,
            next_upcoming,
            target_gw,
            is_active,
        )
        return GameweekContext(
            season=season,
            latest_completed_gameweek=latest_completed,
            target_gameweek=target_gw,
            is_gameweek_active=is_active,
            next_deadline=deadline,
            is_synchronized=True,
            source="fpl_bootstrap",
            status=status,
            current_gameweek=current_gw,
            next_upcoming_gameweek=next_upcoming,
            requested_gameweek=explicit,
            prediction_cutoff=deadline,
            fixture_ids=fixture_ids,
            freshness_status=freshness,
            data_timestamp=data_timestamp,
            completeness=completeness,
            degraded=False,
        )

    if fixtures:
        finished_by_gw: dict[int, list[bool]] = {}
        for fixture in fixtures:
            event = fixture.get("event")
            if event is None:
                continue
            finished_by_gw.setdefault(int(event), []).append(bool(fixture.get("finished", False)))

        completed_gws = [
            gw for gw, flags in finished_by_gw.items() if flags and all(flags)
        ]
        latest_completed = max(completed_gws) if completed_gws else 0
        partial_or_unplayed = sorted(
            gw for gw, flags in finished_by_gw.items() if any(not flag for flag in flags)
        )
        next_upcoming = (
            partial_or_unplayed[0]
            if partial_or_unplayed
            else min(latest_completed + 1, max_gw)
        )
        target_gw = int(explicit) if explicit is not None else next_upcoming
        target_gw = min(max(1, target_gw), max_gw)
        completeness, fixture_ids = _fixture_completeness(fixtures, target_gw)
        status = "historical" if explicit is not None else (
            "partial" if completeness in {"partial", "postponed"} else "synchronized"
        )
        logger.info(
            "GameweekContext from fixtures: completed=%d target=%d completeness=%s",
            latest_completed,
            target_gw,
            completeness,
        )
        return GameweekContext(
            season=season,
            latest_completed_gameweek=latest_completed,
            target_gameweek=target_gw,
            is_gameweek_active=completeness == "partial",
            next_deadline=None,
            is_synchronized=True,
            source="fpl_fixtures",
            status=status,
            current_gameweek=partial_or_unplayed[0] if partial_or_unplayed else None,
            next_upcoming_gameweek=next_upcoming,
            requested_gameweek=explicit,
            prediction_cutoff=None,
            fixture_ids=fixture_ids,
            freshness_status="unknown",
            data_timestamp=data_timestamp,
            completeness=completeness,
            degraded=False,
        )

    if engineered_data is not None and not engineered_data.empty:
        from src.prediction.next_gameweek import find_latest_completed_gameweek

        active_season = season
        if "season" in engineered_data.columns and not engineered_data["season"].empty:
            if season in engineered_data["season"].values:
                season_data = engineered_data[engineered_data["season"] == season]
            else:
                active_season = str(engineered_data["season"].max())
                season_data = engineered_data[engineered_data["season"] == active_season]
        else:
            season_data = engineered_data

        latest_completed = find_latest_completed_gameweek(season_data)
        if latest_completed >= max_gw:
            next_upcoming = 1
        else:
            next_upcoming = latest_completed + 1
        target_gw = int(explicit) if explicit is not None else next_upcoming
        return GameweekContext(
            season=active_season,
            latest_completed_gameweek=latest_completed,
            target_gameweek=min(max(1, target_gw), max_gw),
            is_gameweek_active=False,
            next_deadline=None,
            is_synchronized=True,
            source="engineered_data",
            status="fallback" if explicit is None else "historical",
            current_gameweek=None,
            next_upcoming_gameweek=next_upcoming,
            requested_gameweek=explicit,
            prediction_cutoff=None,
            fixture_ids=(),
            freshness_status="unknown",
            data_timestamp=data_timestamp,
            completeness="unknown",
            degraded=True,
        )

    return GameweekContext(
        season=season,
        latest_completed_gameweek=0,
        target_gameweek=min(max(1, explicit or 1), max_gw),
        is_gameweek_active=False,
        next_deadline=None,
        is_synchronized=True,
        source="default",
        status="fallback",
        current_gameweek=None,
        next_upcoming_gameweek=1,
        requested_gameweek=explicit,
        prediction_cutoff=None,
        fixture_ids=(),
        freshness_status="unknown",
        data_timestamp=data_timestamp,
        completeness="unknown",
        degraded=True,
    )
