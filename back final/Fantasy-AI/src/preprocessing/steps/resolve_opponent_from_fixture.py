"""Preprocessing step resolving opponent_team from fixture information.

**Root-cause fix**: the Vaastav historical dataset's ``opponent_team``
column uses inconsistent representations across seasons — some seasons
store the opponent's real name, others store a small-integer FPL team
ID that is NOT stable across seasons (promoted/relegated clubs cause ID
reuse).  A single global/current-season ID → name mapping cannot
reliably resolve historical data.

**This step's approach** has two tiers:

1. **Seasons WITHOUT ``team`` names** (2016-17 to 2019-20): load each
   season's reference files from the Vaastav repository's extracted
   ``data/<season>/`` directory:
   - ``teams.csv`` → per-season numeric-ID → team-name mapping
   - ``players_raw.csv`` → element (player ID) → numeric team ID
   - ``fixtures.csv`` → fixture ID → (home team ID, away team ID)
   With these, we populate the ``team`` column from the player's
   team ID, and resolve ``opponent_team`` from the fixture's two teams.

2. **Seasons WITH ``team`` names populated** (2020-21+): group rows on
   ``(season, fixture)`` and derive the opponent as "the OTHER team in
   this fixture."

All operations are vectorized (pandas merge/map) for performance on
250K+ row datasets.

**Data-leakage note**: this step resolves only *which* team the
opponent is (a fact known before the match) — it does not use any
match-outcome data (points, goals, etc.).  The chronological shift in
``TeamStrengthStep`` is unaffected.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config.logging_config import get_logger
from src.preprocessing.steps.base import PreprocessingStep, StepSummary

logger = get_logger(__name__)


class ResolveOpponentFromFixtureStep(PreprocessingStep):
    """Resolves ``opponent_team`` from the fixture relationship within each season.

    Args:
        season_column: Column identifying the season.
        fixture_column: Column identifying the fixture (match) within a
            season.
        team_column: Column identifying the player's own team.
        opponent_column: Column to populate with the resolved opponent
            team name.
        vaastav_data_dir: Optional path to the extracted Vaastav
            repository's ``data/`` directory for per-season reference
            files.
    """

    def __init__(
        self,
        season_column: str = "season",
        fixture_column: str = "fixture",
        team_column: str = "team",
        opponent_column: str = "opponent_team",
        vaastav_data_dir: Path | None = None,
    ) -> None:
        self._season_column = season_column
        self._fixture_column = fixture_column
        self._team_column = team_column
        self._opponent_column = opponent_column
        self._vaastav_data_dir = vaastav_data_dir

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "resolve_opponent_from_fixture"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        """Resolve opponent_team from the fixture relationship.

        Args:
            data: The DataFrame to resolve opponents in.

        Returns:
            tuple[pd.DataFrame, StepSummary]: The data with resolved
            opponent_team values and a summary of the resolution.
        """
        rows_before = len(data)
        cleaned = data.copy()

        required = [self._season_column, self._fixture_column]
        missing_cols = [c for c in required if c not in cleaned.columns]
        if missing_cols:
            description = (
                f"Cannot resolve opponents from fixtures; "
                f"missing column(s): {missing_cols}. No changes made."
            )
            logger.warning(description)
            return cleaned, StepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=rows_before,
                description=description,
            )

        # Ensure team and opponent_team columns exist.
        if self._team_column not in cleaned.columns:
            cleaned[self._team_column] = pd.NA
        if self._opponent_column not in cleaned.columns:
            cleaned[self._opponent_column] = pd.NA

        # Ensure columns are object dtype so we can assign strings.
        cleaned[self._opponent_column] = cleaned[self._opponent_column].astype(object)
        cleaned[self._team_column] = cleaned[self._team_column].astype(object)

        # Phase 1: For seasons where team is null, populate team and
        # resolve opponent from per-season Vaastav reference files.
        ref_team_populated = 0
        ref_resolved = 0
        if self._vaastav_data_dir is not None:
            ref_team_populated, ref_resolved = self._resolve_from_reference_files(cleaned)

        # Phase 2: For remaining rows, use fixture grouping.
        fixture_resolved = self._resolve_from_fixture_grouping(cleaned)

        total_resolved = ref_resolved + fixture_resolved
        resolution_pct = (total_resolved / rows_before * 100) if rows_before > 0 else 0.0

        logger.info(
            "Fixture-based opponent resolution: %d/%d rows resolved (%.1f%%). "
            "Reference-file phase: %d team values populated, %d opponents resolved. "
            "Fixture-grouping phase: %d opponents resolved.",
            total_resolved,
            rows_before,
            resolution_pct,
            ref_team_populated,
            ref_resolved,
            fixture_resolved,
        )

        description = (
            f"Resolved {total_resolved}/{rows_before} opponent_team values "
            f"({resolution_pct:.1f}%) from fixture data."
        )

        return cleaned, StepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(cleaned),
            description=description,
        )

    def _resolve_from_reference_files(self, cleaned: pd.DataFrame) -> tuple[int, int]:
        """Populate team and resolve opponent using per-season reference files.

        Uses vectorized pandas operations (map/merge) for performance.

        Args:
            cleaned: The DataFrame to modify in-place.

        Returns:
            tuple[int, int]: (team values populated, opponents resolved).
        """
        total_team_populated = 0
        total_opponent_resolved = 0

        seasons = cleaned[self._season_column].dropna().unique()
        for season in seasons:
            season_mask = cleaned[self._season_column] == season
            season_team_null_count = int((season_mask & cleaned[self._team_column].isna()).sum())

            if season_team_null_count == 0:
                # This season already has team names populated — skip.
                continue

            season_dir = self._vaastav_data_dir / str(season)
            if not season_dir.exists():
                logger.debug("No reference directory for season %s.", season)
                continue

            team_map = self._load_season_team_mapping(season_dir, season)
            if not team_map:
                continue

            # Step 1: Populate team column from element → team_id → team_name.
            player_team_map = self._load_player_team_mapping(season_dir, season)
            if player_team_map and "element" in cleaned.columns:
                elem_to_name = {
                    pid: team_map.get(tid)
                    for pid, tid in player_team_map.items()
                    if team_map.get(tid) is not None
                }
                if elem_to_name:
                    fill_mask = (
                        season_mask
                        & cleaned[self._team_column].isna()
                        & cleaned["element"].notna()
                    )
                    resolved_names = cleaned.loc[fill_mask, "element"].map(elem_to_name)
                    actually_filled = fill_mask & resolved_names.notna()
                    cleaned.loc[actually_filled, self._team_column] = resolved_names[actually_filled]
                    populated = int(actually_filled.sum())
                    total_team_populated += populated
                    logger.info(
                        "Season %s: populated %d team values from players_raw.csv.",
                        season, populated,
                    )

            # Step 2: Resolve opponent from fixture reference data.
            # Build a fixture_id → {team_name: opponent_name} lookup.
            fixture_map = self._load_season_fixture_mapping(season_dir, season, team_map)
            if fixture_map:
                # Vectorized approach: create two helper columns via map.
                season_idx = cleaned.index[season_mask]
                season_fixtures = cleaned.loc[season_idx, self._fixture_column]
                season_teams = cleaned.loc[season_idx, self._team_column]

                # Build a flat lookup: (fixture_id, team_name) → opponent_name
                flat_lookup = {}
                for fid, (home, away) in fixture_map.items():
                    flat_lookup[(fid, home)] = away
                    flat_lookup[(fid, away)] = home

                # Vectorized lookup using zip
                keys = list(zip(
                    season_fixtures.values,
                    season_teams.values,
                ))
                resolved = [flat_lookup.get(_key_safe(k)) for k in keys]

                resolved_series = pd.Series(resolved, index=season_idx)
                can_resolve = resolved_series.notna()
                cleaned.loc[season_idx[can_resolve], self._opponent_column] = (
                    resolved_series[can_resolve].values
                )
                resolved_count = int(can_resolve.sum())
                total_opponent_resolved += resolved_count
                logger.info(
                    "Season %s: resolved %d opponents from fixtures.csv.",
                    season, resolved_count,
                )

        return total_team_populated, total_opponent_resolved

    def _resolve_from_fixture_grouping(self, cleaned: pd.DataFrame) -> int:
        """Resolve opponent by grouping (season, fixture) and finding the other team.

        Only processes rows where opponent_team is still numeric or missing.

        Args:
            cleaned: The DataFrame to modify in-place.

        Returns:
            int: Number of rows resolved.
        """
        has_info = (
            cleaned[self._season_column].notna()
            & cleaned[self._fixture_column].notna()
            & cleaned[self._team_column].notna()
        )

        # Only target rows where opponent is still numeric or missing.
        needs_resolution = has_info & (
            cleaned[self._opponent_column].isna()
            | cleaned[self._opponent_column].apply(_is_numeric_like)
        )

        if not needs_resolution.any():
            return 0

        eligible = cleaned.loc[has_info]
        if eligible.empty:
            return 0

        # Build fixture → {teams} lookup from the data itself.
        fixture_teams = (
            eligible.groupby([self._season_column, self._fixture_column])[self._team_column]
            .apply(lambda s: tuple(sorted(s.unique())))
            .to_dict()
        )

        # Build flat lookup: (season, fixture, team) → opponent
        flat_lookup = {}
        anomalous = 0
        for fixture_key, teams in fixture_teams.items():
            if len(teams) != 2:
                anomalous += 1
                continue
            team_a, team_b = teams
            flat_lookup[(*fixture_key, team_a)] = team_b
            flat_lookup[(*fixture_key, team_b)] = team_a

        if anomalous > 0:
            logger.warning(
                "%d fixture(s) did not have exactly 2 teams and were skipped.",
                anomalous,
            )

        # Vectorized resolution
        target_idx = cleaned.index[needs_resolution]
        keys = list(zip(
            cleaned.loc[target_idx, self._season_column].values,
            cleaned.loc[target_idx, self._fixture_column].values,
            cleaned.loc[target_idx, self._team_column].values,
        ))
        resolved = [flat_lookup.get(k) for k in keys]
        resolved_series = pd.Series(resolved, index=target_idx)
        can_resolve = resolved_series.notna()

        cleaned.loc[target_idx[can_resolve], self._opponent_column] = (
            resolved_series[can_resolve].values
        )
        return int(can_resolve.sum())

    @staticmethod
    def _load_season_team_mapping(season_dir: Path, season: str) -> dict[int, str]:
        """Load numeric team ID → name mapping from a season's teams.csv."""
        teams_path = season_dir / "teams.csv"
        if not teams_path.exists():
            return {}
        try:
            teams = pd.read_csv(teams_path)
            if "id" in teams.columns and "name" in teams.columns:
                mapping = dict(zip(teams["id"].astype(int), teams["name"].astype(str)))
                logger.debug("Season %s: loaded %d team mappings.", season, len(mapping))
                return mapping
        except (OSError, pd.errors.ParserError) as exc:
            logger.warning("Could not load teams.csv for season %s: %s", season, exc)
        return {}

    @staticmethod
    def _load_season_fixture_mapping(
        season_dir: Path, season: str, team_map: dict[int, str]
    ) -> dict[int, tuple[str, str]]:
        """Load fixture ID → (home team name, away team name) mapping."""
        fixtures_path = season_dir / "fixtures.csv"
        if not fixtures_path.exists():
            return {}
        try:
            fixtures = pd.read_csv(fixtures_path)
            required = {"id", "team_h", "team_a"}
            if not required.issubset(fixtures.columns):
                return {}

            result = {}
            for _, row in fixtures.iterrows():
                fid = row["id"]
                th = row["team_h"]
                ta = row["team_a"]
                if pd.notna(fid) and pd.notna(th) and pd.notna(ta):
                    home_name = team_map.get(int(th))
                    away_name = team_map.get(int(ta))
                    if home_name and away_name:
                        result[int(fid)] = (home_name, away_name)
            logger.debug("Season %s: loaded %d fixture mappings.", season, len(result))
            return result
        except (OSError, pd.errors.ParserError, KeyError) as exc:
            logger.warning("Could not load fixtures for season %s: %s", season, exc)
        return {}

    @staticmethod
    def _load_player_team_mapping(season_dir: Path, season: str) -> dict[int, int]:
        """Load player element ID → numeric team ID mapping."""
        players_path = season_dir / "players_raw.csv"
        if not players_path.exists():
            return {}
        try:
            players = pd.read_csv(players_path)
            if "id" in players.columns and "team" in players.columns:
                mapping = dict(
                    zip(players["id"].astype(int), players["team"].astype(int))
                )
                logger.debug(
                    "Season %s: loaded %d player->team mappings.", season, len(mapping)
                )
                return mapping
        except (OSError, pd.errors.ParserError) as exc:
            logger.warning("Could not load players_raw.csv for season %s: %s", season, exc)
        return {}


def _key_safe(key: tuple) -> tuple | None:
    """Convert a lookup key to a safe form, handling NaN/None values.

    Args:
        key: A tuple of (fixture_id, team_name).

    Returns:
        The key with fixture_id cast to int, or None if unusable.
    """
    fid, team = key
    if pd.isna(fid) or pd.isna(team):
        return None
    try:
        return (int(fid), str(team))
    except (ValueError, TypeError):
        return None


def _is_numeric_like(value: object) -> bool:
    """Check if a value looks like a numeric ID rather than a team name.

    Args:
        value: The value to check.

    Returns:
        bool: True if the value appears to be numeric.
    """
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except ValueError:
            return False
    return False
