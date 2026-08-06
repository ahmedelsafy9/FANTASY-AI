"""Data source implementation for the official Fantasy Premier League API.

Provides live, current-season data — specifically, per-player stats
for the most recently *finished* Gameweek — used to keep the
historical dataset up to date without waiting for the Vaastav
repository to be manually updated (see Sprint 9's automation
pipeline).

Two endpoints are used:

- ``bootstrap-static/`` — reference data: every player's identity/team
  and the list of Gameweeks (events), including which one most
  recently finished.
- ``event/{event_id}/live/`` — every player's stats for one specific
  Gameweek.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.common.decorators import retry
from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger
from src.core.exceptions import DataSourceError, DataValidationError
from src.data_collection.interfaces.data_source import DataSource, DataSourceMetadata

logger = get_logger(__name__)

_BOOTSTRAP_FILENAME = "bootstrap_static.json"
_LIVE_EVENT_FILENAME_TEMPLATE = "event_{event_id}_live.json"
_METADATA_FILENAME = "_fpl_api_metadata.json"


class FPLApiDataSource(DataSource):
    """Live FPL data source backed by the official Fantasy Premier League API.

    Args:
        base_url: Base URL of the official FPL API.
        events_path: Relative path of the bootstrap-static endpoint.
        live_event_path_template: Relative path template for a single
            event's live stats, with an ``{event_id}`` placeholder.
        fixtures_path: Relative path of the fixtures endpoint. Used by
            :meth:`get_fixtures` to support fixture-aware prediction
            (Phase 1/3) — kept separate from the ``download()``/``load()``
            historical-ingestion flow since fixtures are consumed
            directly by the prediction and metadata layers, not merged
            into the training dataset.
        timeout_seconds: Per-request timeout, in seconds.
        max_retries: Maximum number of retry attempts for a failed request.
    """

    def __init__(
        self,
        base_url: str,
        events_path: str = "bootstrap-static/",
        live_event_path_template: str = "event/{event_id}/live/",
        fixtures_path: str = "fixtures/",
        timeout_seconds: int = 30,
        max_retries: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._events_path = events_path
        self._live_event_path_template = live_event_path_template
        self._fixtures_path = fixtures_path
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this data source."""
        return "fpl_api"

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    def download(self, destination: Path) -> DataSourceMetadata:
        """Fetch bootstrap reference data and the latest finished event's stats.

        Args:
            destination: Directory the raw JSON payloads should be
                written to.

        Returns:
            DataSourceMetadata: Metadata including which Gameweek
            (event) was fetched.

        Raises:
            DataSourceError: If either request fails, or no finished
                Gameweek is found yet (e.g. before the season starts).
        """
        ensure_directory(destination)

        bootstrap = self._get_json(f"{self._base_url}/{self._events_path}")
        (destination / _BOOTSTRAP_FILENAME).write_text(
            json.dumps(bootstrap), encoding="utf-8"
        )

        latest_event_id = self._find_latest_finished_event(bootstrap)
        if latest_event_id is None:
            raise DataSourceError(
                "No finished Gameweek found in bootstrap-static events; "
                "the season may not have started yet."
            )

        live_path = self._live_event_path_template.format(event_id=latest_event_id)
        live_data = self._get_json(f"{self._base_url}/{live_path}")
        live_filename = _LIVE_EVENT_FILENAME_TEMPLATE.format(event_id=latest_event_id)
        (destination / live_filename).write_text(json.dumps(live_data), encoding="utf-8")

        metadata = DataSourceMetadata(
            name=self.name,
            source_url=self._base_url,
            retrieved_at=datetime.now(timezone.utc),
            records_count=len(live_data.get("elements", [])),
            extra={"latest_finished_event": latest_event_id},
        )
        self._write_metadata(destination, metadata)
        logger.info(
            "Downloaded %s: Gameweek %d, %d player record(s).",
            self.name,
            latest_event_id,
            metadata.records_count,
        )
        return metadata

    def load(self, source_path: Path) -> pd.DataFrame:
        """Load and flatten the latest downloaded Gameweek's player stats.

        Args:
            source_path: Directory previously populated by
                :meth:`download`.

        Returns:
            pd.DataFrame: One row per player for the latest finished
            Gameweek, with columns aligned to the historical dataset's
            schema where possible (``element``, ``name``, ``team``,
            ``GW``, ``season``, ``value``, and every raw stat field).

        Raises:
            DataSourceError: If the expected files are missing or
                cannot be parsed.
        """
        bootstrap_path = source_path / _BOOTSTRAP_FILENAME
        if not bootstrap_path.exists():
            raise DataSourceError(
                f"{_BOOTSTRAP_FILENAME} not found in {source_path}. Call download() first."
            )
        bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))

        latest_event_id = self._find_latest_finished_event(bootstrap)
        if latest_event_id is None:
            raise DataSourceError("No finished Gameweek found in the downloaded bootstrap data.")

        live_filename = _LIVE_EVENT_FILENAME_TEMPLATE.format(event_id=latest_event_id)
        live_path = source_path / live_filename
        if not live_path.exists():
            raise DataSourceError(f"{live_filename} not found in {source_path}. Call download() first.")
        live_data = json.loads(live_path.read_text(encoding="utf-8"))

        team_names = {team["id"]: team.get("name") for team in bootstrap.get("teams", [])}
        players = {p["id"]: p for p in bootstrap.get("elements", [])}
        season = self._infer_season(bootstrap, latest_event_id)

        rows: list[dict[str, Any]] = []
        for element in live_data.get("elements", []):
            player_id = element.get("id")
            stats = dict(element.get("stats", {}))
            player_info = players.get(player_id, {})
            rows.append(
                {
                    "element": player_id,
                    "name": player_info.get("web_name"),
                    "team": team_names.get(player_info.get("team")),
                    "GW": latest_event_id,
                    "season": season,
                    "value": player_info.get("now_cost"),
                    **stats,
                }
            )

        if not rows:
            raise DataSourceError(f"No player rows found for Gameweek {latest_event_id}.")

        frame = pd.DataFrame(rows)
        logger.info("Loaded %d row(s) for Gameweek %d (%s).", len(frame), latest_event_id, season)
        return frame

    def validate(self, data: pd.DataFrame) -> bool:
        """Perform a lightweight structural check on the loaded live data.

        Args:
            data: DataFrame previously produced by :meth:`load`.

        Returns:
            bool: ``True`` if the data passes the structural check.

        Raises:
            DataValidationError: If the data is empty or missing
                critical columns.
        """
        if data.empty:
            raise DataValidationError("Loaded FPL API dataset is empty.")

        required_columns = {"element", "GW", "season", "total_points"}
        missing = required_columns - set(data.columns)
        if missing:
            raise DataValidationError(
                f"FPL API dataset is missing required columns: {sorted(missing)}."
            )

        logger.info("Validation passed: %d rows, %d columns.", *data.shape)
        return True

    def update(self, destination: Path) -> DataSourceMetadata:
        """Re-fetch the latest finished Gameweek and report whether it advanced.

        Args:
            destination: Directory previously populated by
                :meth:`download`.

        Returns:
            DataSourceMetadata: Metadata describing the update,
            including whether a new Gameweek was found.

        Raises:
            DataSourceError: If the refresh fails.
        """
        previous_metadata = self._read_metadata(destination)
        previous_event = (
            previous_metadata.get("extra", {}).get("latest_finished_event")
            if previous_metadata
            else None
        )

        new_metadata = self.download(destination)
        new_event = new_metadata.extra.get("latest_finished_event")

        new_metadata.extra["previous_finished_event"] = previous_event
        new_metadata.extra["advanced"] = previous_event is not None and new_event != previous_event
        self._write_metadata(destination, new_metadata)

        if previous_event == new_event:
            logger.info("Update completed; still at Gameweek %s (no new data).", new_event)
        else:
            logger.info("Update detected new Gameweek: %s -> %s.", previous_event, new_event)

        return new_metadata

    # ------------------------------------------------------------------
    # Fixture-aware prediction support (Phase 1/3)
    # ------------------------------------------------------------------

    def get_teams(self, destination: Path) -> list[dict[str, Any]]:
        """Return the team reference list from a previously downloaded bootstrap.

        This is the authoritative source for mapping a numeric team ID
        (as used by some historical seasons' ``opponent_team`` column,
        and by the live fixtures endpoint) to the team's real name —
        see :mod:`src.data_collection.services.team_mapping_service`.

        Args:
            destination: Directory previously populated by
                :meth:`download`.

        Returns:
            list[dict[str, Any]]: Each team's raw bootstrap-static
            record (includes at least ``id``, ``name``, ``short_name``).

        Raises:
            DataSourceError: If bootstrap-static hasn't been downloaded yet.
        """
        bootstrap_path = destination / _BOOTSTRAP_FILENAME
        if not bootstrap_path.exists():
            raise DataSourceError(
                f"{_BOOTSTRAP_FILENAME} not found in {destination}. Call download() first."
            )
        bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        return list(bootstrap.get("teams", []))

    def get_fixtures(self, future_only: bool = True) -> list[dict[str, Any]]:
        """Fetch fixtures from the live FPL API.

        Each fixture includes (per the FPL API's well-known schema):
        ``event`` (Gameweek number), ``team_h``/``team_a`` (numeric team
        IDs — resolve via :meth:`get_teams`), ``team_h_difficulty``/
        ``team_a_difficulty`` (FPL's own official 1-5 difficulty
        rating), and ``kickoff_time``.

        This is a live, uncached fetch — unlike ``download()``/``load()``,
        fixtures are not persisted as part of the historical dataset
        (they're consumed directly by the prediction and metadata
        layers, which need the *current* fixture list, not a snapshot).

        Args:
            future_only: If ``True``, requests only fixtures that
                haven't been played yet (``finished=false``).

        Returns:
            list[dict[str, Any]]: Raw fixture records.

        Raises:
            DataSourceError: If the request fails.
        """
        url = f"{self._base_url}/{self._fixtures_path}"
        if future_only:
            url = f"{url}?future=1"
        data = self._get_json(url)
        if not isinstance(data, list):
            raise DataSourceError(f"Unexpected fixtures response shape from {url}.")
        logger.info("Fetched %d fixture(s) from %s.", len(data), url)
        return data

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_json(self, url: str) -> Any:
        """GET a URL and parse its JSON body, with retry on transient failures.

        Args:
            url: The URL to fetch.

        Returns:
            Any: The parsed JSON body (a dict for bootstrap-static/live
            endpoints, a list for the fixtures endpoint).

        Raises:
            DataSourceError: If the request fails or returns a
                non-200 status.
        """

        @retry(
            max_attempts=self._max_retries,
            delay_seconds=2.0,
            exceptions=(requests.ConnectionError, requests.Timeout),
        )
        def _do_get() -> Any:
            response = requests.get(url, timeout=self._timeout_seconds)
            if response.status_code != 200:
                raise DataSourceError(f"Unexpected status {response.status_code} fetching {url}.")
            return response.json()

        return _do_get()

    @staticmethod
    def _find_latest_finished_event(bootstrap: dict[str, Any]) -> int | None:
        """Find the highest-numbered finished Gameweek in bootstrap-static events.

        Args:
            bootstrap: The parsed bootstrap-static JSON payload.

        Returns:
            int | None: The latest finished event's ID, or ``None`` if
            none have finished yet.
        """
        finished_events = [
            event["id"] for event in bootstrap.get("events", []) if event.get("finished")
        ]
        return max(finished_events) if finished_events else None

    @staticmethod
    def _infer_season(bootstrap: dict[str, Any], event_id: int) -> str:
        """Infer the season string (e.g. ``"2024-25"``) from an event's deadline.

        The FPL season runs August through May; a deadline in
        July-December implies the season starts that calendar year,
        while January-June implies it started the previous year.

        Args:
            bootstrap: The parsed bootstrap-static JSON payload.
            event_id: The Gameweek to infer the season from.

        Returns:
            str: The inferred season string, or ``"unknown"`` if it
            cannot be determined.
        """
        event = next(
            (e for e in bootstrap.get("events", []) if e.get("id") == event_id), None
        )
        if event is None or not event.get("deadline_time"):
            return "unknown"
        try:
            deadline = datetime.fromisoformat(event["deadline_time"].replace("Z", "+00:00"))
        except ValueError:
            return "unknown"
        start_year = deadline.year if deadline.month >= 7 else deadline.year - 1
        return f"{start_year}-{(start_year + 1) % 100:02d}"

    @staticmethod
    def _write_metadata(destination: Path, metadata: DataSourceMetadata) -> None:
        """Persist metadata to disk so subsequent update() calls can diff it.

        Args:
            destination: Directory the metadata file should live in.
            metadata: Metadata to serialize.
        """
        payload = asdict(metadata)
        payload["retrieved_at"] = (
            metadata.retrieved_at.isoformat() if metadata.retrieved_at else None
        )
        (destination / _METADATA_FILENAME).write_text(
            json.dumps(payload, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _read_metadata(destination: Path) -> dict[str, Any] | None:
        """Read previously persisted metadata, if any.

        Args:
            destination: Directory the metadata file may live in.

        Returns:
            dict[str, Any] | None: The parsed metadata, or ``None`` if
            no metadata file exists yet.
        """
        metadata_path = destination / _METADATA_FILENAME
        if not metadata_path.exists():
            return None
        try:
            return json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read existing metadata at %s: %s", metadata_path, exc)
            return None
