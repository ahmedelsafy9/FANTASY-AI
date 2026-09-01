"""Applies a loaded model to feature rows to produce point predictions."""

from __future__ import annotations

import numpy as np
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
        """Predict the target for each row, with honest uncertainty metrics.

        Two uncertainty-related columns may be added, both statistically
        grounded (never a fabricated "confidence %"):

        - ``model_test_rmse``: the model's own held-out chronological
          test-set RMSE (from training, see ``LoadedModel.metrics``).
          This is a single, MODEL-LEVEL constant — the same for every
          row — so it is context (e.g. "this model is typically off by
          ~1.7 points"), not a per-player differentiator.
        - ``prediction_uncertainty_std``: added ONLY when the
          underlying model is a scikit-learn-style tree ensemble
          exposing ``estimators_`` (e.g. ``RandomForestRegressor``).
          It is the standard deviation of that specific row's
          prediction ACROSS the ensemble's individual trees — a
          genuine, well-established per-prediction uncertainty proxy
          (higher disagreement among trees = less certain prediction).
          For model types that don't expose per-tree predictions
          (e.g. linear models, or when XGBoost/LightGBM aren't
          installed and unavailable), this column is omitted entirely
          rather than filled with an invented placeholder.

        Args:
            rows: A DataFrame containing at least the model's
                ``feature_columns`` (extra columns are preserved
                alongside the prediction, not used as features).

        Returns:
            pd.DataFrame: ``rows`` with an added
            ``predicted_{target_column}`` column, ``model_test_rmse``,
            and (where supported) ``prediction_uncertainty_std``.

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

        model = self._loaded_model.model
        output_column = f"predicted_{self._loaded_model.target_column}"
        result = rows.copy()

        if hasattr(model, "predict_distribution"):
            try:
                dist_df = model.predict_distribution(rows)
                for col in dist_df.columns:
                    result[col] = dist_df[col].to_numpy()
                predictions = dist_df["predicted_total_points"].to_numpy()
            except Exception as exc:
                logger.warning("predict_distribution failed, falling back: %s", exc)
                if hasattr(model, "predict_breakdown"):
                    breakdown_df = model.predict_breakdown(rows)
                    for col in breakdown_df.columns:
                        result[col] = breakdown_df[col].to_numpy()
                    predictions = breakdown_df["predicted_total_points"].to_numpy()
                else:
                    predictions = model.predict(X)
        elif hasattr(model, "predict_breakdown"):
            try:
                breakdown_df = model.predict_breakdown(rows)
                for col in breakdown_df.columns:
                    result[col] = breakdown_df[col].to_numpy()
                predictions = breakdown_df["predicted_total_points"].to_numpy()
            except Exception as exc:
                logger.warning("predict_breakdown failed, falling back to model.predict: %s", exc)
                predictions = model.predict(X)
        else:
            predictions = model.predict(X)

        result[output_column] = predictions
        if "predicted_expected_points" not in result.columns:
            result["predicted_expected_points"] = predictions
        if "predicted_total_points" not in result.columns:
            result["predicted_total_points"] = predictions

        # Canonical aliases
        if "predicted_p_play_any" in result.columns and "predicted_minutes_probability" not in result.columns:
            result["predicted_minutes_probability"] = result["predicted_p_play_any"]
        if "predicted_p_play_60" in result.columns and "predicted_minutes_60_probability" not in result.columns:
            result["predicted_minutes_60_probability"] = result["predicted_p_play_60"]
        if "predicted_clean_sheet_prob" in result.columns and "predicted_clean_sheet_probability" not in result.columns:
            result["predicted_clean_sheet_probability"] = result["predicted_clean_sheet_prob"]

        # Ensure rankings exist even if standard scalar model was used
        if "rank_expected" not in result.columns:
            result["rank_expected"] = (
                pd.Series(result["predicted_expected_points"]).rank(ascending=False, method="min").astype(int).values
            )
        if "rank_upside" not in result.columns and "predicted_p85_points" in result.columns:
            result["rank_upside"] = (
                pd.Series(result["predicted_p85_points"]).rank(ascending=False, method="min").astype(int).values
            )
        if "rank_captaincy" not in result.columns and "captaincy_score" in result.columns:
            result["rank_captaincy"] = (
                pd.Series(result["captaincy_score"]).rank(ascending=False, method="min").astype(int).values
            )

        test_rmse = self._loaded_model.metrics.get("rmse")
        if test_rmse is not None:
            result["model_test_rmse"] = test_rmse

        ensemble_std = self._per_row_ensemble_std(model, X)
        if ensemble_std is not None:
            result["prediction_uncertainty_std"] = ensemble_std

        logger.info(
            "Generated %d prediction(s) using model '%s'.",
            len(result),
            self._loaded_model.model_name,
        )
        return result

    @staticmethod
    def _per_row_ensemble_std(model: object, X: pd.DataFrame) -> np.ndarray | None:
        """Compute per-row prediction std across a tree ensemble's individual trees.

        Args:
            model: The fitted model. Only tree ensembles exposing a
                scikit-learn-style ``estimators_`` list of trees with
                their own ``.predict()`` are supported.
            X: The feature matrix predictions were made for.

        Returns:
            np.ndarray | None: Per-row standard deviation across trees,
            or ``None`` if the model doesn't support this (not an
            error — most model types simply don't expose it).
        """
        estimators = getattr(model, "estimators_", None)
        if not estimators:
            return None
        try:
            tree_predictions = np.stack([tree.predict(X) for tree in estimators], axis=0)
            return np.std(tree_predictions, axis=0)
        except Exception as exc:  # noqa: BLE001 - genuinely optional, never fatal
            logger.debug("Could not compute per-tree ensemble std: %s", exc)
            return None
