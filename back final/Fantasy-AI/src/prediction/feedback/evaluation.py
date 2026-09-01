"""Walk-forward temporal evaluation of the feedback system.

Compares two prediction systems using strict temporal ordering:

    1. **Baseline**: Base DL model prediction only.
    2. **Adaptive**: Base DL prediction + feedback residual correction.

Every evaluation step only uses information available before the target
Gameweek — never the actual result of the Gameweek being predicted.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.prediction.feedback.feedback_analyzer import FeedbackAnalyzer, GlobalMetrics

logger = get_logger(__name__)


@dataclass
class HighScoreMetrics:
    """Metrics for high-score prediction quality.

    Attributes:
        threshold: The point threshold used (e.g. 10, 12).
        n_actual_high: Number of players actually scoring >= threshold.
        precision: Fraction of predicted-high that were actually high.
        recall: Fraction of actually-high that were predicted-high.
        f1: Harmonic mean of precision and recall.
        hit_rate: Fraction of top-N predictions that scored >= threshold.
    """

    threshold: int = 10
    n_actual_high: int = 0
    precision: float = float("nan")
    recall: float = float("nan")
    f1: float = float("nan")
    hit_rate: float = float("nan")

    def to_dict(self) -> dict[str, float]:
        """Convert to a plain dictionary."""
        return {
            "threshold": self.threshold,
            "n_actual_high": self.n_actual_high,
            "precision": self.precision,
            "recall": self.recall,
            "f1": self.f1,
            "hit_rate": self.hit_rate,
        }


@dataclass
class ComparisonResult:
    """Full comparison between baseline and adaptive predictions.

    Attributes:
        baseline_metrics: Global metrics for the base DL model alone.
        adaptive_metrics: Global metrics for the DL + feedback model.
        baseline_high_scores: High-score metrics for the baseline.
        adaptive_high_scores: High-score metrics for the adaptive model.
        per_gw_results: Per-Gameweek comparison table.
        n_gameweeks: Number of Gameweeks evaluated.
    """

    baseline_metrics: GlobalMetrics = field(default_factory=GlobalMetrics)
    adaptive_metrics: GlobalMetrics = field(default_factory=GlobalMetrics)
    baseline_high_scores: list[HighScoreMetrics] = field(default_factory=list)
    adaptive_high_scores: list[HighScoreMetrics] = field(default_factory=list)
    per_gw_results: pd.DataFrame = field(default_factory=pd.DataFrame)
    n_gameweeks: int = 0


class FeedbackEvaluator:
    """Walk-forward evaluator comparing baseline vs adaptive predictions.

    For each evaluated Gameweek N:
    - Uses only feedback from GWs < N.
    - Compares base prediction vs. base + correction vs. actual.
    """

    @staticmethod
    def evaluate_from_feedback(
        feedback: pd.DataFrame,
        min_gameweeks: int = 3,
    ) -> ComparisonResult:
        """Run walk-forward evaluation using accumulated feedback records.

        Each feedback record already contains ``predicted_points`` (base)
        and ``actual_points``. The evaluator simulates applying residual
        corrections using only prior-GW feedback.

        Args:
            feedback: Accumulated feedback with ``GW``, ``predicted_points``,
                ``actual_points``, ``prediction_error``, ``element``.
            min_gameweeks: Minimum GWs of feedback before corrections
                can be applied.

        Returns:
            ComparisonResult: Full baseline vs adaptive comparison.
        """
        if feedback.empty:
            return ComparisonResult()

        fb = feedback.copy()
        fb["GW"] = pd.to_numeric(fb["GW"], errors="coerce")
        fb = fb.dropna(subset=["GW", "predicted_points", "actual_points"])
        fb["predicted_points"] = pd.to_numeric(fb["predicted_points"], errors="coerce")
        fb["actual_points"] = pd.to_numeric(fb["actual_points"], errors="coerce")
        fb["prediction_error"] = pd.to_numeric(fb["prediction_error"], errors="coerce")

        unique_gws = sorted(fb["GW"].unique())
        if len(unique_gws) < min_gameweeks + 1:
            logger.info(
                "Not enough Gameweeks (%d) for walk-forward evaluation (need %d+1).",
                len(unique_gws),
                min_gameweeks,
            )
            return ComparisonResult()

        all_baseline_pred = []
        all_adaptive_pred = []
        all_actual = []
        per_gw_rows = []

        for i, gw in enumerate(unique_gws):
            gw_data = fb[fb["GW"] == gw]
            prior_data = fb[fb["GW"] < gw]

            base_pred = gw_data["predicted_points"].values
            actual = gw_data["actual_points"].values

            all_baseline_pred.extend(base_pred)
            all_actual.extend(actual)

            # Apply simple residual correction using prior mean errors
            if len(prior_data) > 0 and i >= min_gameweeks:
                # Per-player correction from prior errors
                player_corrections = (
                    prior_data.groupby("element")["prediction_error"]
                    .mean()
                    .to_dict()
                )
                # Global correction as fallback
                global_correction = float(prior_data["prediction_error"].mean())

                corrections = np.array([
                    player_corrections.get(elem, global_correction)
                    for elem in gw_data["element"].values
                ])
                # Clip corrections
                corrections = np.clip(corrections, -3.0, 3.0)
                adaptive_pred = base_pred + corrections
            else:
                adaptive_pred = base_pred.copy()

            all_adaptive_pred.extend(adaptive_pred)

            # Per-GW metrics
            gw_base_mae = float(np.mean(np.abs(actual - base_pred)))
            gw_adaptive_mae = float(np.mean(np.abs(actual - adaptive_pred)))
            per_gw_rows.append({
                "GW": gw,
                "n_players": len(gw_data),
                "baseline_mae": gw_base_mae,
                "adaptive_mae": gw_adaptive_mae,
                "improvement": gw_base_mae - gw_adaptive_mae,
            })

        # Compute overall metrics
        baseline_fb = pd.DataFrame({
            "predicted_points": all_baseline_pred,
            "actual_points": all_actual,
        })
        adaptive_fb = pd.DataFrame({
            "predicted_points": all_adaptive_pred,
            "actual_points": all_actual,
        })

        baseline_metrics = FeedbackAnalyzer.compute_global_metrics(baseline_fb)
        adaptive_metrics = FeedbackAnalyzer.compute_global_metrics(adaptive_fb)

        # High-score evaluation
        baseline_high = FeedbackEvaluator._high_score_metrics(
            np.array(all_baseline_pred), np.array(all_actual)
        )
        adaptive_high = FeedbackEvaluator._high_score_metrics(
            np.array(all_adaptive_pred), np.array(all_actual)
        )

        per_gw_df = pd.DataFrame(per_gw_rows)

        return ComparisonResult(
            baseline_metrics=baseline_metrics,
            adaptive_metrics=adaptive_metrics,
            baseline_high_scores=baseline_high,
            adaptive_high_scores=adaptive_high,
            per_gw_results=per_gw_df,
            n_gameweeks=len(unique_gws),
        )

    @staticmethod
    def _high_score_metrics(
        predicted: np.ndarray,
        actual: np.ndarray,
        thresholds: tuple[int, ...] = (10, 12),
        top_ns: tuple[int, ...] = (10, 20),
    ) -> list[HighScoreMetrics]:
        """Compute high-score prediction quality metrics.

        Args:
            predicted: Array of predicted values.
            actual: Array of actual values.
            thresholds: Point thresholds for high-score classification.
            top_ns: Top-N predicted values to evaluate.

        Returns:
            list[HighScoreMetrics]: One entry per threshold.
        """
        results = []

        for threshold in thresholds:
            actually_high = actual >= threshold
            n_actual = int(actually_high.sum())

            if n_actual == 0:
                results.append(HighScoreMetrics(threshold=threshold, n_actual_high=0))
                continue

            # Use the same threshold on predictions for precision/recall
            predicted_high = predicted >= (threshold * 0.6)  # Lower bar for predictions

            tp = int((predicted_high & actually_high).sum())
            fp = int((predicted_high & ~actually_high).sum())
            fn = int((~predicted_high & actually_high).sum())

            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (
                2 * precision * recall / (precision + recall)
                if (precision + recall) > 0
                else 0.0
            )

            # Hit rate: fraction of top-20 predictions that scored >= threshold
            top_n = min(20, len(predicted))
            top_indices = np.argsort(-predicted)[:top_n]
            hits = int(actually_high[top_indices].sum())
            hit_rate = hits / top_n if top_n > 0 else 0.0

            results.append(
                HighScoreMetrics(
                    threshold=threshold,
                    n_actual_high=n_actual,
                    precision=precision,
                    recall=recall,
                    f1=f1,
                    hit_rate=hit_rate,
                )
            )

        return results

    @staticmethod
    def format_comparison(result: ComparisonResult) -> str:
        """Format a comparison result as a human-readable table.

        Args:
            result: The comparison result.

        Returns:
            str: Formatted comparison table.
        """
        lines = [
            "=" * 60,
            "BASELINE vs ADAPTIVE PREDICTION COMPARISON",
            f"({result.n_gameweeks} Gameweeks evaluated)",
            "=" * 60,
            "",
            f"{'Metric':<25} {'Baseline':>12} {'Adaptive':>12} {'Delta':>10}",
            "-" * 60,
        ]

        b = result.baseline_metrics
        a = result.adaptive_metrics

        metrics = [
            ("MAE", b.mae, a.mae, True),
            ("RMSE", b.rmse, a.rmse, True),
            ("R2", b.r2, a.r2, False),
            ("Spearman", b.spearman, a.spearman, False),
            ("Pearson", b.pearson, a.pearson, False),
            ("Mean Signed Error", b.mean_signed_error, a.mean_signed_error, None),
            ("Overpred Rate", b.overprediction_rate, a.overprediction_rate, True),
            ("Underpred Rate", b.underprediction_rate, a.underprediction_rate, True),
        ]

        for name, bv, av, lower_better in metrics:
            delta = av - bv
            if np.isnan(bv) or np.isnan(av):
                lines.append(f"{name:<25} {'N/A':>12} {'N/A':>12} {'N/A':>10}")
            else:
                indicator = ""
                if lower_better is not None:
                    improved = delta < 0 if lower_better else delta > 0
                    indicator = " [+]" if improved else " [-]"
                lines.append(
                    f"{name:<25} {bv:>12.4f} {av:>12.4f} {delta:>+10.4f}{indicator}"
                )

        # High-score metrics
        if result.baseline_high_scores or result.adaptive_high_scores:
            lines.extend(["", "HIGH-SCORE DETECTION", "-" * 60])
            for bh, ah in zip(result.baseline_high_scores, result.adaptive_high_scores):
                lines.append(f"\n  Threshold: actual >= {bh.threshold}")
                lines.append(f"  {'':>15} {'Baseline':>12} {'Adaptive':>12}")
                lines.append(f"  {'Precision':<15} {bh.precision:>12.4f} {ah.precision:>12.4f}")
                lines.append(f"  {'Recall':<15} {bh.recall:>12.4f} {ah.recall:>12.4f}")
                lines.append(f"  {'F1':<15} {bh.f1:>12.4f} {ah.f1:>12.4f}")
                lines.append(f"  {'Hit Rate':<15} {bh.hit_rate:>12.4f} {ah.hit_rate:>12.4f}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)
