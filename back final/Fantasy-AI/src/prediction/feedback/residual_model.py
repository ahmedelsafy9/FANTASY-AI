"""Residual / error correction model.

Learns systematic prediction errors from accumulated feedback and predicts
the expected correction for future predictions. The target variable is:

    residual = actual_points - base_prediction

so a positive prediction means "the base model is likely underpredicting"
and a negative prediction means "the base model is likely overpredicting".

This module implements strict temporal leakage prevention: only feedback
from Gameweeks BEFORE the target Gameweek can be used for training or
feature construction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ResidualModelMetadata:
    """Metadata for a trained residual model.

    Attributes:
        version: Auto-incrementing model version.
        trained_at: ISO timestamp of when the model was trained.
        n_training_samples: Number of feedback records used.
        n_gameweeks: Number of Gameweeks of feedback used.
        feature_columns: Feature columns the model was trained on.
        train_mae: Training set MAE of the residual predictions.
        model_type: Type of model used (e.g. ``"gradient_boosting"``).
        hyperparameters: Model hyperparameters used.
    """

    version: str = "v0"
    trained_at: str = ""
    n_training_samples: int = 0
    n_gameweeks: int = 0
    feature_columns: list[str] = field(default_factory=list)
    train_mae: float = float("nan")
    model_type: str = "gradient_boosting"
    hyperparameters: dict[str, Any] = field(default_factory=dict)


class ResidualModel:
    """Learns to predict systematic prediction errors.

    Architecture:

        feedback history (GW < N) → features → gradient boosting → correction

    The model predicts the expected residual (actual - predicted) and
    applies it as a correction to the base model's prediction.

    Args:
        model_dir: Directory to save/load model artifacts.
        n_estimators: Number of boosting rounds.
        max_depth: Maximum tree depth.
        learning_rate: Boosting learning rate.
        random_state: Random seed.
    """

    # Feature columns that the residual model can use.
    # These are computed from feedback history, never from the target GW.
    HISTORICAL_FEEDBACK_FEATURES = (
        "player_error_mean",
        "player_error_std",
        "player_error_last_3_mean",
        "player_error_last_5_mean",
        "player_abs_error_mean",
        "player_n_feedbacks",
        "position_error_mean",
        "position_abs_error_mean",
        "team_error_mean",
        "team_abs_error_mean",
        "global_error_mean",
        "global_abs_error_mean",
        "recent_underprediction_rate",
        "recent_overprediction_rate",
    )

    def __init__(
        self,
        model_dir: Path,
        n_estimators: int = 100,
        max_depth: int = 4,
        learning_rate: float = 0.05,
        random_state: int = 42,
    ) -> None:
        self._model_dir = model_dir
        self._n_estimators = n_estimators
        self._max_depth = max_depth
        self._learning_rate = learning_rate
        self._random_state = random_state
        self._model: Any = None
        self._metadata = ResidualModelMetadata()
        self._feature_columns: list[str] = []
        ensure_directory(self._model_dir)

    @property
    def is_trained(self) -> bool:
        """Whether the model has been trained."""
        return self._model is not None

    @property
    def metadata(self) -> ResidualModelMetadata:
        """Return the model's metadata."""
        return self._metadata

    @property
    def version(self) -> str:
        """Return the model version string."""
        return self._metadata.version

    def build_residual_features(
        self,
        feedback: pd.DataFrame,
        current_predictions: pd.DataFrame,
        target_gw: int,
        half_life: float = 6.0,
    ) -> pd.DataFrame:
        """Build features for the residual model from historical feedback.

        CRITICAL: only uses feedback from GWs strictly BEFORE ``target_gw``.

        Args:
            feedback: Accumulated feedback records with at least
                ``element``, ``GW``, ``prediction_error``, ``predicted_points``.
            current_predictions: Current base predictions with at least
                ``element`` and prediction value.
            target_gw: The Gameweek being predicted — feedback from this
                GW or later is EXCLUDED.
            half_life: Exponential decay half-life for recency weighting.

        Returns:
            pd.DataFrame: One row per player in ``current_predictions``,
            with historical feedback features attached.
        """
        if feedback.empty:
            return pd.DataFrame()

        # STRICT temporal filter — no leakage
        fb = feedback.copy()
        fb["GW"] = pd.to_numeric(fb["GW"], errors="coerce")
        fb = fb[fb["GW"] < target_gw].copy()

        if fb.empty:
            return pd.DataFrame()

        max_gw = fb["GW"].max()

        # Compute recency weights
        fb["_recency_weight"] = 0.5 ** ((max_gw - fb["GW"]) / half_life)

        features = current_predictions[["element"]].copy()

        # Base prediction feature
        pred_col = None
        for candidate in ("base_prediction", "predicted_total_points"):
            if candidate in current_predictions.columns:
                pred_col = candidate
                break
        if pred_col:
            features["base_prediction"] = current_predictions[pred_col].values

        # Player-level historical error statistics
        player_stats = self._compute_player_stats(fb)
        features = features.merge(player_stats, on="element", how="left")

        # Position-level error statistics
        if "position" in fb.columns and "position" in current_predictions.columns:
            # Add position to features first so we can merge on it
            if "position" not in features.columns:
                features["position"] = current_predictions["position"].values
            pos_stats = self._compute_segment_stats(fb, "position", "position")
            features = features.merge(pos_stats, on="position", how="left")

        # Team-level error statistics
        if "team" in fb.columns and "team" in current_predictions.columns:
            if "team" not in features.columns:
                features["team"] = current_predictions["team"].values
            team_stats = self._compute_segment_stats(fb, "team", "team")
            features = features.merge(team_stats, on="team", how="left")

        # Global error statistics
        global_mean = float(fb["prediction_error"].mean())
        global_abs_mean = float(fb["prediction_error"].abs().mean())
        features["global_error_mean"] = global_mean
        features["global_abs_error_mean"] = global_abs_mean

        # Recent direction rates (using recency-weighted feedback)
        recent = fb.nlargest(min(len(fb), 200), "_recency_weight")
        features["recent_underprediction_rate"] = float(
            (recent["prediction_error"] > 0).mean()
        )
        features["recent_overprediction_rate"] = float(
            (recent["prediction_error"] < 0).mean()
        )

        # Add pre-match features from current predictions if available
        feat_cols = [c for c in current_predictions.columns if c.startswith("feat_")]
        for fc in feat_cols:
            features[fc] = current_predictions[fc].values

        # Fill NaN for players with no history
        features = features.fillna(0.0)

        return features

    def train(
        self,
        feedback: pd.DataFrame,
        half_life: float = 6.0,
        max_gw: int | None = None,
    ) -> ResidualModelMetadata:
        """Train the residual model on accumulated feedback.

        Args:
            feedback: Accumulated feedback records.
            half_life: Exponential decay half-life for sample weighting.
            max_gw: If provided, only use feedback from GWs <= this value.

        Returns:
            ResidualModelMetadata: Metadata about the trained model.
        """
        from sklearn.ensemble import GradientBoostingRegressor

        fb = feedback.copy()
        fb["GW"] = pd.to_numeric(fb["GW"], errors="coerce")

        if max_gw is not None:
            fb = fb[fb["GW"] <= max_gw]

        if fb.empty or len(fb) < 10:
            logger.warning(
                "Insufficient feedback for residual model training (%d records).",
                len(fb),
            )
            return self._metadata

        # Target: prediction_error = actual - predicted
        target = pd.to_numeric(fb["prediction_error"], errors="coerce")
        valid = target.notna()
        fb = fb[valid].copy()
        target = target[valid].values

        # Build training features from historical feedback
        # For each GW in the feedback, compute features using only earlier GWs
        feature_rows = []
        target_values = []

        unique_gws = sorted(fb["GW"].unique())
        if len(unique_gws) < 2:
            logger.warning(
                "Need at least 2 Gameweeks of feedback for residual training."
            )
            return self._metadata

        for gw in unique_gws[1:]:  # Skip first GW — no history to train on
            gw_feedback = fb[fb["GW"] == gw].copy()
            prior_feedback = fb[fb["GW"] < gw].copy()

            if prior_feedback.empty:
                continue

            max_prior_gw = prior_feedback["GW"].max()
            prior_feedback["_recency_weight"] = 0.5 ** (
                (max_prior_gw - prior_feedback["GW"]) / half_life
            )

            # Player stats from prior GWs
            player_stats = self._compute_player_stats(prior_feedback)

            gw_features = gw_feedback[["element"]].copy()
            gw_features["base_prediction"] = pd.to_numeric(
                gw_feedback["predicted_points"], errors="coerce"
            ).values

            gw_features = gw_features.merge(player_stats, on="element", how="left")

            # Global stats
            gw_features["global_error_mean"] = float(
                prior_feedback["prediction_error"].mean()
            )
            gw_features["global_abs_error_mean"] = float(
                prior_feedback["prediction_error"].abs().mean()
            )

            # Position/team stats
            if "position" in prior_feedback.columns and "position" in gw_feedback.columns:
                pos_stats = self._compute_segment_stats(
                    prior_feedback, "position", "position"
                )
                gw_features["position"] = gw_feedback["position"].values
                gw_features = gw_features.merge(pos_stats, on="position", how="left")

            if "team" in prior_feedback.columns and "team" in gw_feedback.columns:
                team_stats = self._compute_segment_stats(
                    prior_feedback, "team", "team"
                )
                gw_features["team"] = gw_feedback["team"].values
                gw_features = gw_features.merge(team_stats, on="team", how="left")

            # Recent rates
            recent = prior_feedback.nlargest(
                min(len(prior_feedback), 200), "_recency_weight"
            )
            gw_features["recent_underprediction_rate"] = float(
                (recent["prediction_error"] > 0).mean()
            )
            gw_features["recent_overprediction_rate"] = float(
                (recent["prediction_error"] < 0).mean()
            )

            gw_features = gw_features.fillna(0.0)

            # Target for this GW
            gw_target = pd.to_numeric(
                gw_feedback["prediction_error"], errors="coerce"
            ).values

            feature_rows.append(gw_features)
            target_values.append(gw_target)

        if not feature_rows:
            logger.warning("No valid training rows for residual model.")
            return self._metadata

        all_features = pd.concat(feature_rows, ignore_index=True)
        all_target = np.concatenate(target_values)

        # Select numeric feature columns only (exclude element, position, team)
        exclude_cols = {"element", "position", "team"}
        self._feature_columns = [
            c for c in all_features.columns
            if c not in exclude_cols
            and pd.api.types.is_numeric_dtype(all_features[c])
        ]

        X = all_features[self._feature_columns].values.astype(np.float32)
        y = all_target.astype(np.float32)

        # Replace any remaining NaN/inf
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # Compute sample weights (exponential decay by GW)
        if "GW" in all_features.columns:
            gw_vals = pd.to_numeric(all_features["GW"], errors="coerce").fillna(0)
        else:
            gw_vals = pd.Series(np.zeros(len(all_features)))
        max_gw_val = gw_vals.max()
        sample_weights = 0.5 ** ((max_gw_val - gw_vals) / half_life)
        sample_weights = sample_weights.values.astype(np.float32)

        # Train gradient boosting regressor
        self._model = GradientBoostingRegressor(
            n_estimators=self._n_estimators,
            max_depth=self._max_depth,
            learning_rate=self._learning_rate,
            random_state=self._random_state,
            subsample=0.8,
        )
        self._model.fit(X, y, sample_weight=sample_weights)

        # Compute training MAE
        train_pred = self._model.predict(X)
        train_mae = float(np.mean(np.abs(y - train_pred)))

        # Update metadata
        existing_version = int(self._metadata.version.replace("v", "")) if self._metadata.version.startswith("v") else 0
        self._metadata = ResidualModelMetadata(
            version=f"v{existing_version + 1}",
            trained_at=datetime.now(timezone.utc).isoformat(),
            n_training_samples=len(y),
            n_gameweeks=len(unique_gws) - 1,
            feature_columns=self._feature_columns,
            train_mae=train_mae,
            model_type="gradient_boosting",
            hyperparameters={
                "n_estimators": self._n_estimators,
                "max_depth": self._max_depth,
                "learning_rate": self._learning_rate,
            },
        )

        logger.info(
            "Trained residual model %s: %d samples, %d GWs, "
            "%d features, train_MAE=%.4f",
            self._metadata.version,
            len(y),
            self._metadata.n_gameweeks,
            len(self._feature_columns),
            train_mae,
        )

        return self._metadata

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        """Predict the expected residual correction.

        Args:
            features: Feature DataFrame with the same columns the model
                was trained on.

        Returns:
            np.ndarray: Predicted corrections (positive = underprediction,
            negative = overprediction).

        Raises:
            RuntimeError: If the model has not been trained.
        """
        if self._model is None:
            raise RuntimeError("ResidualModel has not been trained yet.")

        # Ensure all expected columns exist
        X = pd.DataFrame()
        for col in self._feature_columns:
            if col in features.columns:
                X[col] = pd.to_numeric(features[col], errors="coerce").fillna(0.0)
            else:
                X[col] = 0.0

        X_np = X.values.astype(np.float32)
        X_np = np.nan_to_num(X_np, nan=0.0, posinf=0.0, neginf=0.0)

        return self._model.predict(X_np)

    def save(self, path: Path | None = None) -> Path:
        """Save the trained model and metadata.

        Args:
            path: Directory to save to. Defaults to ``self._model_dir``.

        Returns:
            Path: The directory the model was saved to.
        """
        import joblib

        save_dir = path or self._model_dir
        ensure_directory(save_dir)

        model_path = save_dir / "residual_model.joblib"
        metadata_path = save_dir / "residual_model_metadata.json"

        if self._model is not None:
            joblib.dump(self._model, model_path)

        metadata_dict = {
            "version": self._metadata.version,
            "trained_at": self._metadata.trained_at,
            "n_training_samples": self._metadata.n_training_samples,
            "n_gameweeks": self._metadata.n_gameweeks,
            "feature_columns": self._metadata.feature_columns,
            "train_mae": self._metadata.train_mae,
            "model_type": self._metadata.model_type,
            "hyperparameters": self._metadata.hyperparameters,
        }
        metadata_path.write_text(
            json.dumps(metadata_dict, indent=2), encoding="utf-8"
        )

        logger.info("Saved residual model %s to %s.", self._metadata.version, save_dir)
        return save_dir

    def load(self, path: Path | None = None) -> bool:
        """Load a previously trained model and metadata.

        Args:
            path: Directory to load from. Defaults to ``self._model_dir``.

        Returns:
            bool: True if successfully loaded, False otherwise.
        """
        import joblib

        load_dir = path or self._model_dir
        model_path = load_dir / "residual_model.joblib"
        metadata_path = load_dir / "residual_model_metadata.json"

        if not model_path.exists() or not metadata_path.exists():
            logger.debug("No residual model found at %s.", load_dir)
            return False

        try:
            self._model = joblib.load(model_path)
            raw = json.loads(metadata_path.read_text(encoding="utf-8"))
            self._metadata = ResidualModelMetadata(
                version=raw.get("version", "v0"),
                trained_at=raw.get("trained_at", ""),
                n_training_samples=raw.get("n_training_samples", 0),
                n_gameweeks=raw.get("n_gameweeks", 0),
                feature_columns=raw.get("feature_columns", []),
                train_mae=raw.get("train_mae", float("nan")),
                model_type=raw.get("model_type", "gradient_boosting"),
                hyperparameters=raw.get("hyperparameters", {}),
            )
            self._feature_columns = self._metadata.feature_columns
            logger.info(
                "Loaded residual model %s from %s.", self._metadata.version, load_dir
            )
            return True
        except Exception as exc:
            logger.warning("Could not load residual model from %s: %s", load_dir, exc)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_player_stats(fb: pd.DataFrame) -> pd.DataFrame:
        """Compute per-player historical error statistics.

        Args:
            fb: Historical feedback with ``element`` and ``prediction_error``.

        Returns:
            pd.DataFrame: One row per element with error statistics.
        """
        errors = pd.to_numeric(fb["prediction_error"], errors="coerce")

        player_groups = fb.groupby("element")

        stats = pd.DataFrame({
            "element": player_groups["element"].first().values,
            "player_error_mean": player_groups.apply(
                lambda g: pd.to_numeric(g["prediction_error"], errors="coerce").mean(),
                include_groups=False,
            ).values,
            "player_error_std": player_groups.apply(
                lambda g: pd.to_numeric(g["prediction_error"], errors="coerce").std(),
                include_groups=False,
            ).values,
            "player_abs_error_mean": player_groups.apply(
                lambda g: pd.to_numeric(g["prediction_error"], errors="coerce").abs().mean(),
                include_groups=False,
            ).values,
            "player_n_feedbacks": player_groups.size().values,
        })

        # Last-N error means
        for n in (3, 5):
            col_name = f"player_error_last_{n}_mean"
            last_n_means = player_groups.apply(
                lambda g: pd.to_numeric(g["prediction_error"], errors="coerce").tail(n).mean(),
                include_groups=False,
            )
            stats[col_name] = last_n_means.values

        return stats.fillna(0.0)

    @staticmethod
    def _compute_segment_stats(
        fb: pd.DataFrame,
        segment_col: str,
        output_key: str,
    ) -> pd.DataFrame:
        """Compute per-segment error statistics.

        Args:
            fb: Historical feedback.
            segment_col: Column to group by.
            output_key: Key column name in the output.

        Returns:
            pd.DataFrame: One row per segment value with error statistics.
        """
        groups = fb.groupby(segment_col)
        stats = pd.DataFrame({
            output_key: groups[segment_col].first().values,
            f"{output_key}_error_mean": groups.apply(
                lambda g: pd.to_numeric(g["prediction_error"], errors="coerce").mean(),
                include_groups=False,
            ).values,
            f"{output_key}_abs_error_mean": groups.apply(
                lambda g: pd.to_numeric(g["prediction_error"], errors="coerce").abs().mean(),
                include_groups=False,
            ).values,
        })
        return stats.fillna(0.0)
