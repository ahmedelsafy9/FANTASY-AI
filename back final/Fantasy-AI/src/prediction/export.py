"""Exports prediction results to a clean, sorted CSV file."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.file_utils import atomic_write_csv, ensure_directory
from src.config.logging_config import get_logger

logger = get_logger(__name__)


def export_predictions(
    predictions: pd.DataFrame,
    id_columns: tuple[str, ...],
    prediction_column: str,
    output_path: Path,
) -> pd.DataFrame:
    """Select relevant columns, sort by predicted value, and write to CSV.

    Args:
        predictions: The full predictions DataFrame (including all
            original feature columns).
        id_columns: Identifying/context columns to keep in the export
            (only those actually present are used), e.g.
            ``("element", "name", "team", "value")``.
        prediction_column: Name of the predicted-value column to sort
            by (descending) and include in the export.
        output_path: Destination CSV file path.

    Returns:
        pd.DataFrame: The exact DataFrame written to disk (identifying
        columns, ``predicted_for_gw`` if present, and the prediction
        column), sorted by predicted value descending.
    """
    available_id_columns = [c for c in id_columns if c in predictions.columns]
    extra_columns = [c for c in ("predicted_for_gw",) if c in predictions.columns]
    
    distribution_columns = [
        c
        for c in (
            "predicted_expected_points",
            "predicted_floor_points",
            "predicted_p50_points",
            "predicted_p75_points",
            "predicted_p85_points",
            "predicted_p90_points",
            "predicted_p95_points",
            "predicted_ceiling_points",
            "predicted_upside_points",
            "captaincy_score",
            "rank_expected",
            "rank_upside",
            "rank_captaincy",
            "predicted_p_play_any",
            "predicted_p_play_60",
            "predicted_minutes_probability",
            "predicted_minutes_60_probability",
            "predicted_expected_minutes",
            "predicted_goals",
            "predicted_assists",
            "predicted_clean_sheet_prob",
            "predicted_clean_sheet_probability",
            "predicted_goals_conceded",
            "predicted_saves",
            "predicted_yellow_cards",
            "predicted_red_cards",
            "predicted_bonus",
            "predicted_appearance_points",
            "predicted_goal_points",
            "predicted_assist_points",
            "predicted_clean_sheet_points",
            "predicted_goals_conceded_points",
            "predicted_save_points",
            "predicted_card_points",
            "predicted_bonus_points",
            "prediction_uncertainty_std",
        )
        if c in predictions.columns and c != prediction_column
    ]

    export_columns = (
        available_id_columns
        + extra_columns
        + [prediction_column]
        + distribution_columns
    )
    # Deduplicate while preserving order
    seen = set()
    dedup_export_columns = []
    for col in export_columns:
        if col not in seen and col in predictions.columns:
            seen.add(col)
            dedup_export_columns.append(col)

    export_df = predictions[dedup_export_columns].sort_values(
        by=prediction_column, ascending=False, kind="mergesort"
    )
    export_df = export_df.reset_index(drop=True)

    atomic_write_csv(export_df, output_path)
    logger.info("Exported %d prediction(s) to %s.", len(export_df), output_path)
    return export_df
