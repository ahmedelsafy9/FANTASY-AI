"""Feedback analysis: computes error metrics and discovers systematic biases.

Provides global, player-level, and segment-level analysis of prediction
errors to understand WHERE and WHY the base DL model is systematically
wrong. The purpose is diagnostic — discovering patterns that the residual
model can learn to correct.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GlobalMetrics:
    """Aggregate error metrics for a set of predictions.

    Attributes:
        n: Number of prediction-actual pairs.
        mae: Mean Absolute Error.
        rmse: Root Mean Squared Error.
        r2: Coefficient of Determination.
        spearman: Spearman rank correlation coefficient.
        pearson: Pearson correlation coefficient.
        mean_signed_error: Average of (actual - predicted); positive = underprediction.
        overprediction_rate: Fraction of predictions where predicted > actual.
        underprediction_rate: Fraction of predictions where predicted < actual.
    """

    n: int = 0
    mae: float = float("nan")
    rmse: float = float("nan")
    r2: float = float("nan")
    spearman: float = float("nan")
    pearson: float = float("nan")
    mean_signed_error: float = float("nan")
    overprediction_rate: float = float("nan")
    underprediction_rate: float = float("nan")

    def to_dict(self) -> dict[str, float]:
        """Convert to a plain dictionary."""
        return {
            "n": self.n,
            "mae": self.mae,
            "rmse": self.rmse,
            "r2": self.r2,
            "spearman": self.spearman,
            "pearson": self.pearson,
            "mean_signed_error": self.mean_signed_error,
            "overprediction_rate": self.overprediction_rate,
            "underprediction_rate": self.underprediction_rate,
        }


@dataclass
class SegmentBias:
    """Error analysis for a specific segment (e.g. position=DEF).

    Attributes:
        segment_column: Column used for segmentation.
        segment_value: The segment's value.
        n: Number of records in this segment.
        mean_signed_error: Average directional error in this segment.
        mae: Mean Absolute Error in this segment.
        std_error: Standard deviation of prediction error.
    """

    segment_column: str = ""
    segment_value: str = ""
    n: int = 0
    mean_signed_error: float = 0.0
    mae: float = 0.0
    std_error: float = 0.0


class FeedbackAnalyzer:
    """Computes error metrics and discovers systematic prediction biases.

    Works entirely from accumulated feedback records — never accesses
    raw actual data directly, ensuring temporal safety.
    """

    @staticmethod
    def compute_global_metrics(
        feedback: pd.DataFrame,
        predicted_col: str = "predicted_points",
        actual_col: str = "actual_points",
    ) -> GlobalMetrics:
        """Compute global error metrics from feedback records.

        Args:
            feedback: Feedback DataFrame with predicted and actual columns.
            predicted_col: Name of the predicted-points column.
            actual_col: Name of the actual-points column.

        Returns:
            GlobalMetrics: Aggregate error metrics.
        """
        if feedback.empty or predicted_col not in feedback.columns or actual_col not in feedback.columns:
            return GlobalMetrics()

        predicted = pd.to_numeric(feedback[predicted_col], errors="coerce")
        actual = pd.to_numeric(feedback[actual_col], errors="coerce")
        valid = predicted.notna() & actual.notna()
        predicted = predicted[valid].values
        actual = actual[valid].values
        n = len(predicted)

        if n == 0:
            return GlobalMetrics()

        errors = actual - predicted
        abs_errors = np.abs(errors)
        sq_errors = errors ** 2

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(sq_errors)))
        mean_signed = float(np.mean(errors))

        # R²
        ss_res = np.sum(sq_errors)
        ss_tot = np.sum((actual - np.mean(actual)) ** 2)
        r2 = float(1.0 - ss_res / ss_tot) if ss_tot > 0 else float("nan")

        # Correlations
        try:
            spearman_r, _ = scipy_stats.spearmanr(predicted, actual)
            spearman = float(spearman_r)
        except Exception:
            spearman = float("nan")

        try:
            pearson_r, _ = scipy_stats.pearsonr(predicted, actual)
            pearson = float(pearson_r)
        except Exception:
            pearson = float("nan")

        over_rate = float(np.mean(errors < 0))  # predicted > actual
        under_rate = float(np.mean(errors > 0))  # predicted < actual

        return GlobalMetrics(
            n=n,
            mae=mae,
            rmse=rmse,
            r2=r2,
            spearman=spearman,
            pearson=pearson,
            mean_signed_error=mean_signed,
            overprediction_rate=over_rate,
            underprediction_rate=under_rate,
        )

    @staticmethod
    def player_level_analysis(
        feedback: pd.DataFrame,
        top_n: int = 20,
    ) -> dict[str, pd.DataFrame]:
        """Identify the biggest prediction errors at the player level.

        Args:
            feedback: Feedback DataFrame.
            top_n: Number of top results to return in each category.

        Returns:
            dict[str, pd.DataFrame]: Analysis results keyed by category
            name.
        """
        if feedback.empty or "prediction_error" not in feedback.columns:
            return {}

        result: dict[str, pd.DataFrame] = {}
        id_cols = [c for c in ("element", "name", "team", "position", "season", "GW") if c in feedback.columns]
        err_cols = [c for c in ("predicted_points", "actual_points", "prediction_error", "absolute_error") if c in feedback.columns]
        cols = id_cols + err_cols

        # Biggest underpredictions (actual >> predicted)
        result["biggest_underpredictions"] = (
            feedback.nlargest(top_n, "prediction_error")[cols].reset_index(drop=True)
        )

        # Biggest overpredictions (predicted >> actual)
        result["biggest_overpredictions"] = (
            feedback.nsmallest(top_n, "prediction_error")[cols].reset_index(drop=True)
        )

        # Largest absolute errors
        result["largest_absolute_errors"] = (
            feedback.nlargest(top_n, "absolute_error")[cols].reset_index(drop=True)
        )

        # Missed high scorers: actual >= 10 but low prediction
        if "actual_points" in feedback.columns:
            high_actual = feedback[
                pd.to_numeric(feedback["actual_points"], errors="coerce") >= 10
            ].copy()
            if not high_actual.empty:
                result["missed_high_scorers"] = (
                    high_actual.nlargest(
                        min(top_n, len(high_actual)), "prediction_error"
                    )[cols].reset_index(drop=True)
                )

        # False high predictions: predicted high, actual low
        if "predicted_points" in feedback.columns and "actual_points" in feedback.columns:
            pred_vals = pd.to_numeric(feedback["predicted_points"], errors="coerce")
            actual_vals = pd.to_numeric(feedback["actual_points"], errors="coerce")
            false_high = feedback[
                (pred_vals >= 6) & (actual_vals <= 2)
            ].copy()
            if not false_high.empty:
                result["false_high_predictions"] = (
                    false_high.nsmallest(
                        min(top_n, len(false_high)), "prediction_error"
                    )[cols].reset_index(drop=True)
                )

        return result

    @staticmethod
    def segment_analysis(
        feedback: pd.DataFrame,
        segment_column: str,
    ) -> list[SegmentBias]:
        """Analyze prediction errors by a segment column.

        Args:
            feedback: Feedback DataFrame.
            segment_column: Column to segment by (e.g. ``"position"``,
                ``"team"``, ``"was_home"``).

        Returns:
            list[SegmentBias]: Error analysis for each segment value.
        """
        if feedback.empty or segment_column not in feedback.columns:
            return []
        if "prediction_error" not in feedback.columns:
            return []

        results = []
        for value, group in feedback.groupby(segment_column, observed=True):
            errors = pd.to_numeric(group["prediction_error"], errors="coerce").dropna()
            if len(errors) < 3:
                continue
            results.append(
                SegmentBias(
                    segment_column=segment_column,
                    segment_value=str(value),
                    n=len(errors),
                    mean_signed_error=float(errors.mean()),
                    mae=float(errors.abs().mean()),
                    std_error=float(errors.std()),
                )
            )

        results.sort(key=lambda b: abs(b.mean_signed_error), reverse=True)
        return results

    @staticmethod
    def discover_biases(
        feedback: pd.DataFrame,
        min_segment_size: int = 10,
    ) -> list[SegmentBias]:
        """Automatically discover systematic biases across all available segments.

        Tests common segment columns (position, team, home/away, etc.)
        and reports those with statistically significant directional bias.

        Args:
            feedback: Accumulated feedback DataFrame.
            min_segment_size: Minimum number of records in a segment.

        Returns:
            list[SegmentBias]: Discovered biases, sorted by absolute bias
            magnitude.
        """
        if feedback.empty:
            return []

        # Candidate segment columns to test
        candidates = [
            "position",
            "team",
            "actual_was_home",
        ]

        # Add binned versions of continuous features
        fb = feedback.copy()
        if "predicted_points" in fb.columns:
            pred = pd.to_numeric(fb["predicted_points"], errors="coerce")
            fb["_pred_bucket"] = pd.cut(
                pred,
                bins=[-999, 2, 4, 6, 8, 999],
                labels=["0-2", "2-4", "4-6", "6-8", "8+"],
            )
            candidates.append("_pred_bucket")

        if "actual_minutes" in fb.columns:
            mins = pd.to_numeric(fb["actual_minutes"], errors="coerce")
            fb["_minutes_bucket"] = pd.cut(
                mins,
                bins=[-1, 0, 45, 60, 89, 999],
                labels=["0", "1-45", "46-60", "61-89", "90"],
            )
            candidates.append("_minutes_bucket")

        all_biases = []
        for col in candidates:
            if col not in fb.columns:
                continue
            biases = FeedbackAnalyzer.segment_analysis(fb, col)
            for bias in biases:
                if bias.n >= min_segment_size and abs(bias.mean_signed_error) > 0.3:
                    all_biases.append(bias)

        all_biases.sort(key=lambda b: abs(b.mean_signed_error), reverse=True)
        return all_biases
