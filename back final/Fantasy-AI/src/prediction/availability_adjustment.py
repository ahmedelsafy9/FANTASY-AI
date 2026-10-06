"""Availability-aware prediction adjustment.

Takes the merged predictions DataFrame (which now includes availability
columns from Phase 1) and adjusts expected-points predictions to
reflect actual player availability, injury status, and expected minutes.

Design principles:
- The original model prediction is PRESERVED as ``predicted_expected_points_raw``.
- The adjusted prediction replaces ``predicted_expected_points`` and
  becomes the authoritative value used by all downstream consumers
  (top players, captain, squad builder, differentials).
- The ``availability_adjustment_factor`` column makes the adjustment
  transparent and debuggable.
"""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)

# Prediction columns to adjust (in order of preference).
_PREDICTION_COLUMNS = (
    "predicted_expected_points",
    "predicted_total_points",
    "score_d",
    "predicted_fpl_rank_score",
)

# Columns that should also be scaled by the availability multiplier.
_SECONDARY_COLUMNS = (
    "predicted_p75_points",
    "predicted_p85_points",
    "predicted_p90_points",
    "predicted_p95_points",
    "predicted_ceiling_points",
    "predicted_upside_points",
    "captaincy_score",
    "ceiling_p75",
    "ceiling_p85",
    "ceiling_p90",
)


def _compute_adjustment_factor(row: pd.Series) -> float:
    """Compute the availability adjustment factor for a single player row.

    Maps ``availability_status`` and ``availability_expected_minutes``
    to a multiplier in [0.0, 1.0].

    The factor represents:  P(plays) × (expected_minutes / baseline_minutes)

    Returns:
        float: A multiplier ∈ [0.0, 1.0].
    """
    status = str(row.get("availability_status", "fit")).lower()

    # Hard zeros
    if status in ("unavailable", "suspended", "ruled_out", "major_injury"):
        return 0.0

    # Use expected_minutes vs baseline
    expected_mins = row.get("availability_expected_minutes")
    if expected_mins is not None and expected_mins == 0.0:
        return 0.0

    chance = row.get("chance_of_playing_next_round")

    if status == "fit":
        return 1.0

    if status == "rotation_risk":
        # Moderate discount
        if chance is not None:
            return max(0.2, chance / 100.0)
        return 0.75

    if status == "doubtful":
        if chance is not None:
            return max(0.1, chance / 100.0)
        return 0.50

    if status == "minor_injury":
        if chance is not None:
            return max(0.05, chance / 100.0)
        return 0.25

    # Unknown status — no adjustment
    return 1.0


def adjust_predictions_for_availability(
    predictions: pd.DataFrame,
) -> pd.DataFrame:
    """Adjust prediction scores to reflect player availability.

    Modifies the DataFrame **in place** (and also returns it).

    For each player:
    1. The original prediction is saved to ``{col}_raw``.
    2. An ``availability_adjustment_factor`` is computed from the
       availability status and chance-of-playing.
    3. The prediction is multiplied by the factor.

    Players with ``availability_status == "fit"`` receive a factor
    of 1.0 (no change).

    Args:
        predictions: The merged predictions DataFrame, expected to
            contain ``availability_status`` and (optionally)
            ``chance_of_playing_next_round`` and
            ``availability_expected_minutes`` columns.

    Returns:
        The same DataFrame, with adjusted predictions.
    """
    if "availability_status" not in predictions.columns:
        logger.info(
            "No availability_status column found; skipping prediction adjustment."
        )
        return predictions

    # Compute adjustment factor for each row
    predictions["availability_adjustment_factor"] = predictions.apply(
        _compute_adjustment_factor, axis=1
    )

    # Find the primary prediction column
    primary_col = None
    for col in _PREDICTION_COLUMNS:
        if col in predictions.columns:
            primary_col = col
            break

    if primary_col is None:
        logger.warning(
            "No recognized prediction column found (%s); "
            "cannot apply availability adjustment.",
            _PREDICTION_COLUMNS,
        )
        return predictions

    # Preserve raw prediction
    raw_col = f"{primary_col}_raw"
    if raw_col not in predictions.columns:
        predictions[raw_col] = predictions[primary_col].copy()

    # Apply adjustment to primary
    predictions[primary_col] = (
        predictions[raw_col]
        * predictions["availability_adjustment_factor"]
    )

    # Also adjust secondary columns
    for sec_col in _SECONDARY_COLUMNS:
        if sec_col in predictions.columns:
            sec_raw = f"{sec_col}_raw"
            if sec_raw not in predictions.columns:
                predictions[sec_raw] = predictions[sec_col].copy()
            predictions[sec_col] = (
                predictions[sec_raw]
                * predictions["availability_adjustment_factor"]
            )

    # Log summary
    adjusted_count = (
        predictions["availability_adjustment_factor"] < 1.0
    ).sum()
    zeroed_count = (
        predictions["availability_adjustment_factor"] == 0.0
    ).sum()

    logger.info(
        "Availability adjustment applied: %d player(s) adjusted "
        "(of which %d zeroed out), %d unchanged.",
        adjusted_count,
        zeroed_count,
        len(predictions) - adjusted_count,
    )

    return predictions
