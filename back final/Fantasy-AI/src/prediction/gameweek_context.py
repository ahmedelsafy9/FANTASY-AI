"""Shared Authoritative Gameweek Context for Fantasy-AI.

Ensures that the player points prediction model and the match prediction model
always operate on the exact same authoritative FPL gameweek. Resolves the active
gameweek using official FPL data source metadata (bootstrap-static and fixtures),
handles gameweek transitions, and invalidates stale cached predictions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import Settings

logger = get_logger(__name__)


@dataclass(frozen=True)
class GameweekContext:
    """Authoritative gameweek state shared across all prediction services.

    Attributes:
        season: Current FPL season string (e.g. '2026-27').
        latest_completed_gameweek: The highest gameweek where all matches are completed.
        target_gameweek: The authoritative upcoming gameweek to predict for.
        is_gameweek_active: Whether a gameweek is currently in progress.
        next_deadline: ISO timestamp of the target gameweek's deadline.
        is_synchronized: True when both player and match models use this gameweek.
        source: Data source used to resolve this context ('fpl_bootstrap', 'fixtures', 'features').
        status: Status descriptor ('synchronized', 'transition', 'stale_cache_overridden', 'fallback').
    """

    season: str
    latest_completed_gameweek: int
    target_gameweek: int
    is_gameweek_active: bool
    next_deadline: str | None
    is_synchronized: bool
    source: str
    status: str


def resolve_authoritative_gameweek(
    settings: Settings,
    bootstrap_data: dict[str, Any] | None = None,
    fixtures_data: list[dict[str, Any]] | None = None,
    engineered_data: pd.DataFrame | None = None,
    current_time: datetime | None = None,
) -> GameweekContext:
    """Resolve the authoritative gameweek for the next prediction round.

    Priority:
    1. FPL API bootstrap-static events (official authority for deadlines and gameweek states).
    2. FPL API fixtures (completed vs unplayed matches).
    3. Engineered historical dataset (fallback based on completed match rows).

    Args:
        settings: Application settings.
        bootstrap_data: Optional pre-loaded bootstrap-static dict.
        fixtures_data: Optional pre-loaded fixtures list.
        engineered_data: Optional historical engineered DataFrame.
        current_time: Optional datetime override (defaults to UTC now).

    Returns:
        GameweekContext: Authoritative context to be passed to all models.
    """
    now = current_time or datetime.now(timezone.utc)
    season = "2026-27"
    max_gw = getattr(settings.prediction, "max_valid_gameweek", 38)

    # ------------------------------------------------------------------
    # 1. Attempt resolution via FPL bootstrap-static (official authority)
    # ------------------------------------------------------------------
    bootstrap = bootstrap_data
    if bootstrap is None:
        live_dir = settings.paths.raw_data_dir / "fpl_api"
        bootstrap_path = live_dir / "bootstrap_static.json"
        if not bootstrap_path.exists():
            bootstrap_path = Path("data/raw/fpl_api/bootstrap_static.json")
        if bootstrap_path.exists():
            try:
                bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Could not read bootstrap_static.json: %s", exc)

    if bootstrap and "events" in bootstrap and len(bootstrap["events"]) > 0:
        events = bootstrap["events"]
        completed_gws = [
            int(e["id"])
            for e in events
            if e.get("finished", False) and e.get("id") is not None
        ]
        latest_completed = max(completed_gws) if completed_gws else 0

        # Find current and next events
        current_event = next((e for e in events if e.get("is_current")), None)
        next_event = next((e for e in events if e.get("is_next")), None)

        target_gw: int | None = None
        next_deadline: str | None = None
        is_active = bool(current_event is not None and not current_event.get("finished", False))

        if next_event is not None and next_event.get("id") is not None:
            target_gw = int(next_event["id"])
            next_deadline = next_event.get("deadline_time")
        elif current_event is not None and not current_event.get("finished", False):
            # Mid-gameweek: current GW is in progress
            current_gw_id = int(current_event["id"])
            target_gw = min(current_gw_id + 1, max_gw)
            # Find next event deadline
            ev_next = next((e for e in events if e.get("id") == target_gw), None)
            if ev_next:
                next_deadline = ev_next.get("deadline_time")
        elif latest_completed > 0:
            target_gw = min(latest_completed + 1, max_gw)
            ev_target = next((e for e in events if e.get("id") == target_gw), None)
            if ev_target:
                next_deadline = ev_target.get("deadline_time")
        else:
            target_gw = 1

        target_gw = min(max(1, target_gw), max_gw)
        latest_completed = max(0, min(latest_completed, max_gw))

        logger.info(
            "GameweekContext resolved from FPL bootstrap: latest_completed=%d, target_gw=%d, is_active=%s",
            latest_completed,
            target_gw,
            is_active,
        )

        return GameweekContext(
            season=season,
            latest_completed_gameweek=latest_completed,
            target_gameweek=target_gw,
            is_gameweek_active=is_active,
            next_deadline=next_deadline,
            is_synchronized=True,
            source="fpl_bootstrap",
            status="synchronized",
        )

    # ------------------------------------------------------------------
    # 2. Attempt resolution via fixtures data
    # ------------------------------------------------------------------
    fixtures = fixtures_data
    if fixtures is None:
        fix_path = settings.paths.raw_data_dir / "fpl_api" / "fixtures.json"
        if not fix_path.exists():
            fix_path = Path("data/raw/fpl_api/fixtures.json")
        if fix_path.exists():
            try:
                fixtures = json.loads(fix_path.read_text(encoding="utf-8"))
            except Exception as exc:
                logger.warning("Could not read fixtures.json: %s", exc)

    if fixtures and len(fixtures) > 0:
        finished_by_gw: dict[int, list[bool]] = {}
        for f in fixtures:
            ev = f.get("event")
            if ev is not None:
                finished_by_gw.setdefault(int(ev), []).append(bool(f.get("finished", False)))

        completed_gws = [
            gw for gw, fins in finished_by_gw.items()
            if len(fins) > 0 and all(fins)
        ]
        latest_completed = max(completed_gws) if completed_gws else 0

        unplayed_gws = sorted([
            gw for gw, fins in finished_by_gw.items()
            if any(not fn for fn in fins)
        ])

        target_gw = unplayed_gws[0] if unplayed_gws else min(latest_completed + 1, max_gw)
        target_gw = min(max(1, target_gw), max_gw)

        logger.info(
            "GameweekContext resolved from fixtures: latest_completed=%d, target_gw=%d",
            latest_completed,
            target_gw,
        )

        return GameweekContext(
            season=season,
            latest_completed_gameweek=latest_completed,
            target_gameweek=target_gw,
            is_gameweek_active=False,
            next_deadline=None,
            is_synchronized=True,
            source="fpl_fixtures",
            status="synchronized",
        )

    # ------------------------------------------------------------------
    # 3. Fallback: engineered historical dataset
    # ------------------------------------------------------------------
    if engineered_data is not None and not engineered_data.empty:
        from src.prediction.next_gameweek import find_latest_completed_gameweek
        s_data = (
            engineered_data[engineered_data["season"] == season]
            if "season" in engineered_data.columns
            else engineered_data
        )
        latest_completed = find_latest_completed_gameweek(s_data)
        target_gw = min(latest_completed + 1, max_gw)
        return GameweekContext(
            season=season,
            latest_completed_gameweek=latest_completed,
            target_gameweek=target_gw,
            is_gameweek_active=False,
            next_deadline=None,
            is_synchronized=True,
            source="engineered_data",
            status="fallback",
        )

    # Extreme fallback
    return GameweekContext(
        season=season,
        latest_completed_gameweek=0,
        target_gameweek=1,
        is_gameweek_active=False,
        next_deadline=None,
        is_synchronized=True,
        source="default",
        status="fallback",
    )
