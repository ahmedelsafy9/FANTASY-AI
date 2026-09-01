"""Feedback adapter: orchestrates the full feedback correction pipeline.

Connects the snapshot store, feedback store, residual model, and cold-start
logic into a single interface that the automation pipeline calls to produce
corrected predictions.

Architecture:

    base prediction → load historical feedback → build residual features →
    residual model prediction → clip correction → final prediction
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import FeedbackSettings
from src.prediction.feedback.feedback_store import FeedbackStore
from src.prediction.feedback.residual_model import ResidualModel

logger = get_logger(__name__)


class FeedbackAdapter:
    """Orchestrates the full feedback correction pipeline.

    Given base predictions from the DL model, this adapter:
    1. Loads accumulated historical feedback (strictly from prior GWs).
    2. Checks cold-start conditions.
    3. Builds residual features.
    4. Gets correction from the residual model.
    5. Caps correction at ±max_correction.
    6. Returns predictions with correction and confidence columns.

    Args:
        feedback_store: Store for loading accumulated feedback.
        residual_model: Trained (or loadable) residual model.
        settings: Feedback-specific settings.
    """

    def __init__(
        self,
        feedback_store: FeedbackStore,
        residual_model: ResidualModel,
        settings: FeedbackSettings,
    ) -> None:
        self._feedback_store = feedback_store
        self._residual_model = residual_model
        self._settings = settings

    def apply_correction(
        self,
        base_predictions: pd.DataFrame,
        season: str,
        target_gw: int,
        prediction_column: str = "predicted_total_points",
        base_model_version: str = "unknown",
    ) -> pd.DataFrame:
        """Apply feedback correction to base predictions.

        If insufficient feedback history exists (cold start), returns
        predictions with zero correction and zero confidence.

        Args:
            base_predictions: DataFrame with at least ``element`` and
                the prediction column.
            season: Current season identifier.
            target_gw: The Gameweek being predicted.
            prediction_column: Column containing the base prediction.
            base_model_version: Version of the base model.

        Returns:
            pd.DataFrame: Copy of ``base_predictions`` with added columns:
            ``base_prediction``, ``feedback_correction``,
            ``final_prediction``, ``feedback_confidence``,
            ``base_model_version``, ``feedback_model_version``.
        """
        result = base_predictions.copy()

        # Ensure base_prediction column exists
        result["base_prediction"] = pd.to_numeric(
            result[prediction_column], errors="coerce"
        ).fillna(0.0)
        result["base_model_version"] = base_model_version

        # Load all feedback from prior GWs (strict temporal filter)
        feedback = self._feedback_store.load_feedback(
            season=season, max_gw=target_gw - 1
        )

        # Cold-start check
        if not self._has_sufficient_feedback(feedback, target_gw):
            logger.info(
                "Insufficient feedback for %s GW%d — returning base predictions "
                "(cold start).",
                season,
                target_gw,
            )
            result["feedback_correction"] = 0.0
            result["final_prediction"] = result["base_prediction"]
            result["feedback_confidence"] = 0.0
            result["feedback_model_version"] = "none"
            return result

        # Ensure residual model is trained/loaded
        if not self._residual_model.is_trained:
            loaded = self._residual_model.load()
            if not loaded:
                logger.info(
                    "No residual model available — returning base predictions."
                )
                result["feedback_correction"] = 0.0
                result["final_prediction"] = result["base_prediction"]
                result["feedback_confidence"] = 0.0
                result["feedback_model_version"] = "none"
                return result

        # Build residual features
        features = self._residual_model.build_residual_features(
            feedback=feedback,
            current_predictions=result,
            target_gw=target_gw,
            half_life=float(self._settings.feedback_half_life),
        )

        if features.empty:
            logger.info(
                "Could not build residual features — returning base predictions."
            )
            result["feedback_correction"] = 0.0
            result["final_prediction"] = result["base_prediction"]
            result["feedback_confidence"] = 0.0
            result["feedback_model_version"] = self._residual_model.version
            return result

        # Get corrections from residual model
        try:
            raw_corrections = self._residual_model.predict(features)
        except Exception as exc:
            logger.warning(
                "Residual model prediction failed: %s — returning base predictions.",
                exc,
            )
            result["feedback_correction"] = 0.0
            result["final_prediction"] = result["base_prediction"]
            result["feedback_confidence"] = 0.0
            result["feedback_model_version"] = self._residual_model.version
            return result

        # Clip corrections
        max_corr = self._settings.max_correction
        clipped = np.clip(raw_corrections, -max_corr, max_corr)

        # Match corrections to result rows by element
        correction_df = pd.DataFrame({
            "element": features["element"].values,
            "_correction": clipped,
        })
        result = result.merge(correction_df, on="element", how="left")
        result["feedback_correction"] = result["_correction"].fillna(0.0)
        result.drop(columns=["_correction"], inplace=True, errors="ignore")

        # Final prediction
        result["final_prediction"] = (
            result["base_prediction"] + result["feedback_correction"]
        )

        # Confidence
        result["feedback_confidence"] = self._compute_confidence(
            feedback, target_gw
        )

        result["feedback_model_version"] = self._residual_model.version

        n_corrected = (result["feedback_correction"].abs() > 0.01).sum()
        logger.info(
            "Applied feedback corrections for %s GW%d: %d/%d players corrected, "
            "mean_correction=%.3f, confidence=%.3f",
            season,
            target_gw,
            n_corrected,
            len(result),
            result["feedback_correction"].mean(),
            result["feedback_confidence"].mean(),
        )

        return result

    def update_model(
        self,
        season: str,
        latest_completed_gw: int,
    ) -> bool:
        """Train/retrain the residual model with all available feedback.

        Args:
            season: Season identifier.
            latest_completed_gw: The most recent completed GW — only
                feedback up to and including this GW is used.

        Returns:
            bool: True if the model was successfully trained.
        """
        feedback = self._feedback_store.load_feedback(
            season=season, max_gw=latest_completed_gw
        )

        if feedback.empty:
            logger.info("No feedback available — cannot train residual model.")
            return False

        n_gws = feedback["GW"].nunique() if "GW" in feedback.columns else 0
        if n_gws < self._settings.min_feedback_gameweeks:
            logger.info(
                "Only %d Gameweek(s) of feedback — need %d for training.",
                n_gws,
                self._settings.min_feedback_gameweeks,
            )
            return False

        if len(feedback) < self._settings.min_feedback_records:
            logger.info(
                "Only %d feedback records — need %d for training.",
                len(feedback),
                self._settings.min_feedback_records,
            )
            return False

        metadata = self._residual_model.train(
            feedback=feedback,
            half_life=float(self._settings.feedback_half_life),
            max_gw=latest_completed_gw,
        )

        if self._residual_model.is_trained:
            self._residual_model.save()
            logger.info(
                "Residual model %s trained and saved.", metadata.version
            )
            return True

        return False

    def _has_sufficient_feedback(
        self,
        feedback: pd.DataFrame,
        target_gw: int,
    ) -> bool:
        """Check whether there is enough feedback for meaningful correction.

        Args:
            feedback: Accumulated feedback.
            target_gw: The target GW.

        Returns:
            bool: True if minimum thresholds are met.
        """
        if feedback.empty:
            return False

        n_records = len(feedback)
        n_gws = feedback["GW"].nunique() if "GW" in feedback.columns else 0

        return (
            n_gws >= self._settings.min_feedback_gameweeks
            and n_records >= self._settings.min_feedback_records
        )

    def _compute_confidence(
        self,
        feedback: pd.DataFrame,
        target_gw: int,
    ) -> float:
        """Compute a feedback confidence score.

        Confidence ranges from 0.0 (no evidence) to 1.0 (high evidence
        with stable residuals). Based on:

        1. Number of feedback GWs available (sigmoid ramp).
        2. Stability of residual variance across GWs.
        3. Volume of evidence.

        Args:
            feedback: Accumulated feedback.
            target_gw: Target Gameweek.

        Returns:
            float: Confidence score in [0, 1].
        """
        if feedback.empty:
            return 0.0

        n_gws = feedback["GW"].nunique() if "GW" in feedback.columns else 0
        ramp = self._settings.confidence_ramp_gameweeks

        # Sigmoid ramp: 0 at 0 GWs, ~0.5 at ramp/2, ~0.88 at ramp
        gw_factor = 1.0 / (1.0 + np.exp(-6.0 * (n_gws / max(ramp, 1) - 0.5)))

        # Stability: compare residual std across GWs
        if "GW" in feedback.columns and n_gws >= 2:
            gw_stds = (
                feedback.groupby("GW")["prediction_error"]
                .apply(lambda x: pd.to_numeric(x, errors="coerce").std())
            )
            cv = float(gw_stds.std() / max(gw_stds.mean(), 0.01))
            stability_factor = 1.0 / (1.0 + cv)
        else:
            stability_factor = 0.5

        # Volume factor
        n_records = len(feedback)
        min_records = self._settings.min_feedback_records
        volume_factor = min(1.0, n_records / max(min_records * 3, 1))

        confidence = float(
            0.5 * gw_factor + 0.3 * stability_factor + 0.2 * volume_factor
        )
        return min(1.0, max(0.0, confidence))
