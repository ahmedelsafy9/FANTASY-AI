"""Applies a loaded model to feature rows to produce point predictions."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.core.exceptions import PredictionError
from src.prediction.loader import LoadedModel

logger = get_logger(__name__)


class PredictionService:
    """Produces predictions from a :class:`~src.prediction.loader.LoadedModel`.

    Reconstructs the exact feature vector the model was trained on
    (same columns, same order, same imputation) before calling
    ``model.predict()`` — this is the whole reason the training layer
    persists ``feature_columns`` and ``train_medians`` alongside the
    model artifact.

    Args:
        loaded_model: The model and its reproducibility metadata.
    """

    def __init__(self, loaded_model: LoadedModel) -> None:
        self._loaded_model = loaded_model

    def predict(self, rows: pd.DataFrame) -> pd.DataFrame:
        """Predict the target for each row.

        Args:
            rows: A DataFrame containing at least the model's
                ``feature_columns`` (extra columns are preserved
                alongside the prediction, not used as features).

        Returns:
            pd.DataFrame: ``rows`` with an added
            ``predicted_{target_column}`` column.

        Raises:
            PredictionError: If a required feature column is entirely
                absent from ``rows`` (as opposed to merely having some
                missing values, which are imputed).
        """
        missing_columns = [
            c for c in self._loaded_model.feature_columns if c not in rows.columns
        ]
        if missing_columns:
            raise PredictionError(
                f"Input data is missing required feature column(s): {missing_columns}."
            )

        X = rows[self._loaded_model.feature_columns].apply(pd.to_numeric, errors="coerce")
        X = X.fillna(self._loaded_model.train_medians)
        remaining_na = X.isna().sum()
        still_missing = remaining_na[remaining_na > 0]
        if not still_missing.empty:
            # A column with no training-set median (unseen at train time) — fall
            # back to 0 rather than leaving NaN, which would break prediction.
            X = X.fillna(0)
            logger.warning(
                "No training median available for column(s) %s; filled with 0.",
                list(still_missing.index),
            )

        predictions = self._loaded_model.model.predict(X)

        output_column = f"predicted_{self._loaded_model.target_column}"
        result = rows.copy()
        result[output_column] = predictions
        logger.info(
            "Generated %d prediction(s) using model '%s'.",
            len(result),
            self._loaded_model.model_name,
        )
        return result
