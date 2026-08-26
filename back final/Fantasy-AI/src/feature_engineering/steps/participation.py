"""Feature step deriving player participation, starts, and minutes signals without leakage."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps._common import chronological_sort_key, resolve_column
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class PlayerParticipationStep(FeatureStep):
    """Derives player participation signals from historical minutes and starts.

    Produces:
    - ``prev_gw_minutes``: Minutes played in the previous gameweek (shifted by 1).
    - ``prev_gw_played``: 1.0 if previous match minutes > 0, 0.0 if 0, NaN if no prior match.
    - ``prev_gw_started``: 1.0 if started previous match, 0.0 if sub/unused, NaN if no prior match.
    - ``prev_gw_bench_unused``: 1.0 if previous match minutes == 0, 0.0 if played, NaN if no prior match.
    - ``starts_last_{window}``: Rolling average of starts over recent windows.
    - ``bench_unused_last_{window}``: Rolling average of unused bench appearances over recent windows.

    All features use ``shift(1)`` within player groups before rolling to guarantee no data leakage.

    Args:
        player_id_columns: Candidate columns identifying a player.
        chronological_columns: Candidate columns defining match order (e.g. ``("season", "GW")``).
        minutes_columns: Candidate column names for minutes played.
        starts_columns: Candidate column names for starts.
        windows: Rolling window sizes for participation metrics (default: (3, 5)).
    """

    def __init__(
        self,
        player_id_columns: tuple[str, ...],
        chronological_columns: tuple[str, ...],
        minutes_columns: tuple[str, ...] = ("minutes",),
        starts_columns: tuple[str, ...] = ("starts",),
        windows: tuple[int, ...] = (3, 5),
    ) -> None:
        self._player_id_columns = player_id_columns
        self._chronological_columns = chronological_columns
        self._minutes_columns = minutes_columns
        self._starts_columns = starts_columns
        self._windows = windows

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "player_participation"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Compute player participation and availability features.

        Args:
            data: Input DataFrame.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: Data with new participation columns
            and execution summary.
        """
        rows_before = len(data)
        player_id_column = resolve_column(self._player_id_columns, data)
        sort_columns = chronological_sort_key(data, self._chronological_columns)
        minutes_col = resolve_column(self._minutes_columns, data)
        starts_col = resolve_column(self._starts_columns, data)

        expected_columns = [
            "prev_gw_minutes",
            "prev_gw_played",
            "prev_gw_started",
            "prev_gw_bench_unused",
        ]
        for w in self._windows:
            expected_columns.extend([
                f"starts_last_{w}",
                f"bench_unused_last_{w}",
            ])

        if player_id_column is None or minutes_col is None:
            logger.warning(
                "Missing player_id (%s) or minutes column (%s); filling participation features with NaN.",
                player_id_column,
                minutes_col,
            )
            working = data.copy()
            for col in expected_columns:
                working[col] = pd.NA
            return working, FeatureStepSummary(
                step_name=self.name,
                rows_before=rows_before,
                rows_after=len(working),
                columns_added=expected_columns,
                description="Required columns missing; filled all participation outputs with NaN.",
            )

        working = data.copy()
        working["__original_order__"] = range(len(working))
        sort_by = [player_id_column, *sort_columns]
        working = working.sort_values(by=sort_by, kind="mergesort")

        # Clean numeric minutes
        minutes_series = pd.to_numeric(working[minutes_col], errors="coerce").fillna(0.0)

        # Derive starts series (use starts_col if available, fallback to minutes >= 60 where starts is null)
        if starts_col is not None and starts_col in working.columns:
            raw_starts = pd.to_numeric(working[starts_col], errors="coerce")
            inferred_starts = (minutes_series >= 60).astype(float)
            starts_series = raw_starts.fillna(inferred_starts)
            starts_series = (starts_series > 0).astype(float)
        else:
            starts_series = (minutes_series >= 60).astype(float)

        # Bench unused: player row exists with 0 minutes played
        bench_unused_series = (minutes_series == 0).astype(float)
        played_series = (minutes_series > 0).astype(float)

        # Grouped and shifted values
        grouped_player = working[player_id_column]
        prev_minutes = minutes_series.groupby(grouped_player).shift(1)
        prev_starts = starts_series.groupby(grouped_player).shift(1)
        prev_played = played_series.groupby(grouped_player).shift(1)
        prev_bench_unused = bench_unused_series.groupby(grouped_player).shift(1)

        working["prev_gw_minutes"] = prev_minutes
        working["prev_gw_played"] = prev_played
        working["prev_gw_started"] = prev_starts
        working["prev_gw_bench_unused"] = prev_bench_unused

        for w in self._windows:
            working[f"starts_last_{w}"] = prev_starts.groupby(grouped_player).transform(
                lambda s, win=w: s.rolling(window=win, min_periods=1).mean()
            )
            working[f"bench_unused_last_{w}"] = prev_bench_unused.groupby(grouped_player).transform(
                lambda s, win=w: s.rolling(window=win, min_periods=1).mean()
            )

        working = working.sort_values(by="__original_order__", kind="mergesort")
        working = working.drop(columns="__original_order__")
        working.index = data.index

        summary = FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=expected_columns,
            description=f"Added {len(expected_columns)} player participation column(s).",
        )
        logger.info(summary.description)
        return working, summary
