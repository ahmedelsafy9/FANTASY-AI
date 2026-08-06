"""Exports prediction results to a clean, sorted CSV file."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.common.file_utils import ensure_directory
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
    export_columns = available_id_columns + extra_columns + [prediction_column]

    export_df = predictions[export_columns].sort_values(
        by=prediction_column, ascending=False, kind="mergesort"
    )
    export_df = export_df.reset_index(drop=True)

    ensure_directory(output_path.parent)
    export_df.to_csv(output_path, index=False)
    logger.info("Exported %d prediction(s) to %s.", len(export_df), output_path)
    return export_df
