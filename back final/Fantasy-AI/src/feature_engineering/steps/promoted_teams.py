"""Feature step deriving promoted team flags and player prior-season historical performance."""

from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import resolve_column
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class PromotedAndHistoricalStep(FeatureStep):
    """Derives promoted-team indicators and player prior-season history signals.

    Features derived:
    - ``is_promoted_team``: 1.0 if player's team was promoted into PL this season, 0.0 otherwise.
    - ``opponent_is_promoted_team``: 1.0 if opponent team was promoted into PL this season, 0.0 otherwise.
    - ``player_is_new_to_pl``: 1.0 if player had 0 minutes across all prior seasons, 0.0 otherwise.
    - ``prev_season_minutes``: Total minutes played in the immediate prior season (S-1).
    - ``prev_season_points``: Total points scored in the immediate prior season (S-1).
    - ``prev_season_matches``: Total appearances (>0 mins) in the immediate prior season (S-1).
    - ``prev_season_ppm``: Points per match in the immediate prior season (S-1).

    Guarantees zero leakage by strictly aggregating statistics only from seasons strictly preceding
    the current row's season.

    Args:
        team_column: Column name for player's team.
        opponent_column: Column name for opponent's team.
        season_column: Column name for season identifier (e.g. ``"2022-23"``).
        player_id_columns: Candidate columns identifying a player (in priority order).
        minutes_columns: Candidate columns for minutes played.
        points_columns: Candidate columns for total points.
        master_team_list_path: Optional path to master team list CSV.
    """

    def __init__(
        self,
        team_column: str = "team",
        opponent_column: str = "opponent_team",
        season_column: str = "season",
        player_id_columns: tuple[str, ...] = ("name_normalized", "name", "element"),
        minutes_columns: tuple[str, ...] = ("minutes",),
        points_columns: tuple[str, ...] = ("total_points",),
        master_team_list_path: Path | None = None,
    ) -> None:
        self._team_column = team_column
        self._opponent_column = opponent_column
        self._season_column = season_column
        self._player_id_columns = player_id_columns
        self._minutes_columns = minutes_columns
        self._points_columns = points_columns
        self._master_team_list_path = master_team_list_path

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "promoted_and_historical"

    def _get_promoted_teams_by_season(
        self, seasons: list[str], data: pd.DataFrame
    ) -> dict[str, set[str]]:
        """Determine promoted teams for each season."""
        # Try loading from master_team_list if available
        if self._master_team_list_path and Path(self._master_team_list_path).exists():
            try:
                mt_df = pd.read_csv(self._master_team_list_path)
                all_seasons = sorted(mt_df["season"].dropna().unique())
                promoted: dict[str, set[str]] = {}
                for i, s in enumerate(all_seasons):
                    if i == 0:
                        promoted[s] = set()
                    else:
                        prev_s = all_seasons[i - 1]
                        curr_teams = set(mt_df[mt_df["season"] == s]["team_name"].dropna().unique())
                        prev_teams = set(mt_df[mt_df["season"] == prev_s]["team_name"].dropna().unique())
                        promoted[s] = curr_teams - prev_teams
                return promoted
            except Exception as exc:
                logger.warning("Failed to load master team list (%s); falling back to data.", exc)

        # Fallback: derive from dataset teams
        season_teams: dict[str, set[str]] = {}
        if self._team_column in data.columns:
            for s in seasons:
                t_set = set(data[data[self._season_column] == s][self._team_column].dropna().unique())
                season_teams[s] = t_set

        promoted = {}
        for i, s in enumerate(seasons):
            if i == 0 or s not in season_teams:
                promoted[s] = set()
            else:
                prev_s = seasons[i - 1]
                prev_set = season_teams.get(prev_s, set())
                promoted[s] = season_teams[s] - prev_set if prev_set else set()
        return promoted

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Compute promoted team and historical prior-season features.

        Args:
            data: Input DataFrame.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: Transformed DataFrame and summary.
        """
        rows_before = len(data)
        columns_added = [
            "is_promoted_team",
            "opponent_is_promoted_team",
            "player_is_new_to_pl",
            "prev_season_minutes",
            "prev_season_points",
            "prev_season_matches",
            "prev_season_ppm",
        ]

        if self._season_column not in data.columns:
            logger.warning("Season column '%s' missing; filling outputs with NaN.", self._season_column)
            working = data.copy()
            for col in columns_added:
                working[col] = pd.NA
            return working, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(working),
                columns_added=columns_added,
                description="Season column missing; filled outputs with NaN.",
            )

        working = data.copy()
        working["__original_order__"] = range(len(working))

        seasons = sorted(working[self._season_column].dropna().unique())
        promoted_map = self._get_promoted_teams_by_season(seasons, working)

        # Promoted team indicators
        if self._team_column in working.columns:
            working["is_promoted_team"] = working.apply(
                lambda r: 1.0 if r[self._team_column] in promoted_map.get(r[self._season_column], set()) else 0.0,
                axis=1,
            )
        else:
            working["is_promoted_team"] = 0.0

        if self._opponent_column in working.columns:
            working["opponent_is_promoted_team"] = working.apply(
                lambda r: 1.0 if r[self._opponent_column] in promoted_map.get(r[self._season_column], set()) else 0.0,
                axis=1,
            )
        else:
            working["opponent_is_promoted_team"] = 0.0

        # Player prior season historical performance
        player_id = resolve_column(self._player_id_columns, working)
        minutes_col = resolve_column(self._minutes_columns, working)
        points_col = resolve_column(self._points_columns, working)

        if player_id is not None and minutes_col is not None and points_col is not None:
            # Clean numeric values
            working_clean = working[[player_id, self._season_column]].copy()
            working_clean["_minutes"] = pd.to_numeric(working[minutes_col], errors="coerce").fillna(0.0)
            working_clean["_points"] = pd.to_numeric(working[points_col], errors="coerce").fillna(0.0)
            working_clean["_played"] = (working_clean["_minutes"] > 0).astype(float)

            # Aggregate per player per season
            season_agg = working_clean.groupby([player_id, self._season_column]).agg(
                s_mins=("_minutes", "sum"),
                s_pts=("_points", "sum"),
                s_apps=("_played", "sum"),
            ).reset_index()

            # Build prior season stats mapping
            lookup_records = []
            for p_id, p_df in season_agg.groupby(player_id):
                p_seasons = set(p_df[self._season_column])
                p_by_season = {r[self._season_column]: r for _, r in p_df.iterrows()}
                cum_mins = 0.0
                for i, s in enumerate(seasons):
                    if s not in p_seasons:
                        continue
                    prev_s = seasons[i - 1] if i > 0 else None
                    prev_rec = p_by_season.get(prev_s)
                    prev_m = float(prev_rec["s_mins"]) if prev_rec is not None else 0.0
                    prev_p = float(prev_rec["s_pts"]) if prev_rec is not None else 0.0
                    prev_a = float(prev_rec["s_apps"]) if prev_rec is not None else 0.0
                    prev_ppm = prev_p / max(1.0, prev_a) if prev_a > 0 else 0.0
                    is_new = 1.0 if cum_mins == 0.0 else 0.0

                    lookup_records.append({
                        player_id: p_id,
                        self._season_column: s,
                        "prev_season_minutes": prev_m,
                        "prev_season_points": prev_p,
                        "prev_season_matches": prev_a,
                        "prev_season_ppm": prev_ppm,
                        "player_is_new_to_pl": is_new,
                    })
                    curr_rec = p_by_season[s]
                    cum_mins += float(curr_rec["s_mins"])

            if lookup_records:
                lookup_df = pd.DataFrame(lookup_records)
                working = working.merge(lookup_df, on=[player_id, self._season_column], how="left")
            else:
                for col in ["prev_season_minutes", "prev_season_points", "prev_season_matches", "prev_season_ppm"]:
                    working[col] = 0.0
                working["player_is_new_to_pl"] = 1.0
        else:
            for col in ["prev_season_minutes", "prev_season_points", "prev_season_matches", "prev_season_ppm"]:
                working[col] = 0.0
            working["player_is_new_to_pl"] = 1.0

        # Fill any missing values safely with defaults
        working["prev_season_minutes"] = working["prev_season_minutes"].fillna(0.0)
        working["prev_season_points"] = working["prev_season_points"].fillna(0.0)
        working["prev_season_matches"] = working["prev_season_matches"].fillna(0.0)
        working["prev_season_ppm"] = working["prev_season_ppm"].fillna(0.0)
        working["player_is_new_to_pl"] = working["player_is_new_to_pl"].fillna(1.0)

        working = working.sort_values(by="__original_order__", kind="mergesort")
        working = working.drop(columns="__original_order__")
        working.index = data.index

        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=columns_added,
            description=f"Added {len(columns_added)} promoted team and historical season column(s).",
        )
        logger.info(summary.description)
        return working, summary
