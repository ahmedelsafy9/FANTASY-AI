"""Prediction query service: serves precomputed next-Gameweek predictions.

Kept free of any HTTP-framework dependency so it can be unit tested
directly, and so the API layer stays a thin translation layer over it.
"""

from __future__ import annotations

from dataclasses import dataclass
import decimal
from decimal import Decimal, ROUND_HALF_UP
import json

import pandas as pd

from src.config.logging_config import get_logger
from src.core.exceptions import PlayerNotFoundError

logger = get_logger(__name__)


@dataclass
class CaptainRecommendation:
    """A captain pick recommendation.

    Attributes:
        player: The recommended player's row, as a dict.
        reasoning: A short, human-readable explanation of the pick.
        pool_size: How many players were considered for the pick.
    """

    player: dict
    reasoning: str
    pool_size: int


class PredictionQueryService:
    """Serves queries over a precomputed next-Gameweek predictions table.

    Args:
        predictions: The full predictions DataFrame, as produced by
            :class:`~src.prediction.predictor.PredictionService` (i.e.
            including every engineered feature column, not just the
            trimmed CSV export columns) — this is what lets
            :meth:`get_captain` filter on columns like a minutes
            average.
        player_id_column: The resolved player identifier column.
        prediction_column: The column holding the predicted value
            (e.g. ``"predicted_total_points"``).
    """

    def __init__(
        self,
        predictions: pd.DataFrame,
        player_id_column: str,
        prediction_column: str,
    ) -> None:
        self._predictions = predictions.sort_values(
            by=prediction_column, ascending=False, kind="mergesort"
        ).reset_index(drop=True)
        self._player_id_column = player_id_column
        self._prediction_column = prediction_column

    def get_all(self) -> pd.DataFrame:
        """Return every player's prediction, sorted highest to lowest.

        Returns:
            pd.DataFrame: The full predictions table.
        """
        return self._predictions

    def get_by_player(self, player_id: str) -> dict:
        """Fetch a single player's prediction by identifier.

        Args:
            player_id: The player identifier as received from the API.

        Returns:
            dict: The player's prediction row as a JSON-serializable dict.

        Raises:
            PlayerNotFoundError: If no player matches ``player_id``.
        """
        id_as_string = self._predictions[self._player_id_column].astype(str)
        matches = self._predictions[id_as_string == str(player_id)]
        if matches.empty:
            raise PlayerNotFoundError(f"No prediction found for player '{player_id}'.")
        return _row_to_dict(matches.iloc[0])

    def get_top(self, limit: int) -> list[dict]:
        """Return the top ``limit`` players by predicted value.

        Args:
            limit: Maximum number of players to return.

        Returns:
            list[dict]: The top predictions, highest first.
        """
        top = self._predictions.head(limit)
        return [_row_to_dict(row) for _, row in top.iterrows()]

    def get_captain(
        self,
        minutes_columns: tuple[str, ...],
        min_minutes_avg: float,
    ) -> CaptainRecommendation:
        """Recommend a captain pick, preferring reliable starters.

        Filters to players whose recent average minutes (the first
        available column from ``minutes_columns``) meets
        ``min_minutes_avg`` before picking the highest predicted
        scorer — captaining a player who might not start is a common
        real-world mistake this filter exists to avoid. Falls back to
        the unfiltered pool (with a note in the reasoning) if no
        minutes column is available or nobody clears the threshold.

        Args:
            minutes_columns: Candidate columns holding a recent
                average-minutes feature (e.g.
                ``("minutes_avg_last_3",)``).
            min_minutes_avg: Minimum recent average minutes required
                to be considered a reliable starter.

        Returns:
            CaptainRecommendation: The recommended player, reasoning,
            and the size of the pool considered.

        Raises:
            PlayerNotFoundError: If there are no predictions at all.
        """
        if self._predictions.empty:
            raise PlayerNotFoundError("No predictions available to choose a captain from.")

        minutes_column = next(
            (c for c in minutes_columns if c in self._predictions.columns), None
        )

        if minutes_column is None:
            pool = self._predictions
            reasoning = (
                "No minutes-history column was available, so the pick considers all "
                "players regardless of recent playing time."
            )
        else:
            pool = self._predictions[
                pd.to_numeric(self._predictions[minutes_column], errors="coerce")
                >= min_minutes_avg
            ]
            if pool.empty:
                logger.warning(
                    "No players met the minimum minutes threshold (%.1f); falling back "
                    "to the full pool.",
                    min_minutes_avg,
                )
                pool = self._predictions
                reasoning = (
                    f"No player met the reliable-starter threshold "
                    f"({minutes_column} >= {min_minutes_avg}), so the pick falls back "
                    "to the highest predicted scorer overall."
                )
            else:
                reasoning = (
                    f"Highest predicted scorer among players averaging at least "
                    f"{min_minutes_avg} minutes recently ({minutes_column})."
                )

        best = pool.sort_values(
            by=self._prediction_column, ascending=False, kind="mergesort"
        ).iloc[0]

        return CaptainRecommendation(
            player=_row_to_dict(best), reasoning=reasoning, pool_size=len(pool)
        )


def _is_missing(value: object) -> bool:
    """Check if a scalar value represents a missing value (None, NaN, NaT).

    Containers (lists, dicts, tuples, sets) are never treated as scalar missing values.
    """
    if value is None:
        return True
    if isinstance(value, (list, tuple, dict, set, pd.Series, pd.DataFrame)):
        return False
    try:
        return bool(pd.isna(value))
    except (ValueError, TypeError):
        return False


def _to_native(value: object) -> object:
    """Recursively convert pandas/numpy types and nested containers to built-in Python types for JSON.

    Args:
        value: A scalar or container value.

    Returns:
        object: Built-in Python primitive (dict, list, int, float, str, bool, None).
    """
    if _is_missing(value):
        return None

    if isinstance(value, dict):
        return {k: _to_native(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_native(v) for v in value]

    if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
        try:
            return [_to_native(v) for v in value.tolist()]
        except (ValueError, TypeError):
            pass

    if hasattr(value, "item"):
        try:
            val = value.item()
            if _is_missing(val):
                return None
            return val
        except (ValueError, TypeError):
            pass

    return value


def _round_prediction(value: object) -> int | None:
    """Round a predicted points value to the nearest integer using standard half-up rounding.

    Examples:
        7.384 -> 7
        5.921 -> 6
        10.147 -> 10
        10.5 -> 11
        -10.5 -> -11
    """
    if _is_missing(value):
        return None
    try:
        val_float = float(value)  # type: ignore[arg-type]
        return int(
            Decimal(str(val_float)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
    except (ValueError, TypeError, decimal.InvalidOperation):
        return value  # type: ignore[return-value]


def _row_to_dict(row: pd.Series) -> dict:
    """Convert a pandas row to a JSON-serializable dict (NaN -> None).

    Safely handles nested containers (like upcoming_fixtures lists) without
    raising ValueError on pandas missing-value checks.

    For backward compatibility, ``predicted_total_points`` is rounded to
    an integer at this serialization boundary. All other distribution quantiles
    (e.g. ``predicted_expected_points``, ``predicted_p85_points``, ``captaincy_score``),
    event predictions (e.g. ``predicted_goals``), and breakdowns retain exact
    floating-point precision.

    Args:
        row: The row to convert.

    Returns:
        dict: The row as a plain dict of built-in Python types.
    """
    res = {}
    for key, value in row.items():
        native_val = _to_native(value)
        if key == "prediction_signals" and isinstance(native_val, str):
            try:
                res[key] = json.loads(native_val)
            except Exception:
                res[key] = native_val
        elif key == "predicted_total_points":
            res[key] = _round_prediction(native_val)
        elif isinstance(key, str) and isinstance(native_val, float):
            res[key] = round(native_val, 4)
        else:
            res[key] = native_val

    # Ensure canonical aliases
    if "predicted_p_play_any" in res and "predicted_minutes_probability" not in res:
        res["predicted_minutes_probability"] = res["predicted_p_play_any"]
    if "predicted_p_play_60" in res and "predicted_minutes_60_probability" not in res:
        res["predicted_minutes_60_probability"] = res["predicted_p_play_60"]
    if "predicted_clean_sheet_prob" in res and "predicted_clean_sheet_probability" not in res:
        res["predicted_clean_sheet_probability"] = res["predicted_clean_sheet_prob"]

    # Construct points breakdown dict if individual component columns exist
    if "predicted_appearance_points" in res or "predicted_goal_points" in res:
        res["points_breakdown"] = {
            "appearance_points": res.get("predicted_appearance_points", 0.0),
            "goal_points": res.get("predicted_goal_points", 0.0),
            "assist_points": res.get("predicted_assist_points", 0.0),
            "clean_sheet_points": res.get("predicted_clean_sheet_points", 0.0),
            "goals_conceded_points": res.get("predicted_goals_conceded_points", 0.0),
            "save_points": res.get("predicted_save_points", 0.0),
            "card_points": res.get("predicted_card_points", 0.0),
            "bonus_points": res.get("predicted_bonus_points", 0.0),
            "total_points": res.get("predicted_expected_points", res.get("predicted_total_points", 0.0)),
        }

    return res
