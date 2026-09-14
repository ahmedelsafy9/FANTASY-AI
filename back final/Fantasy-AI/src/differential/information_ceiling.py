"""Information ceiling analysis for differential prediction.

Diagnostic tool: Not used in production or inference.
Measures the gap between:
    1. Pre-GW Information (What our model and baselines know)
    2. Oracle A: Knows exact same-GW playing time (minutes)
    3. Oracle B: Knows exact same-GW offensive actions (xG, xA, shots)

Reveals whether the performance limit is due to model architecture or the
fundamental unpredictability of football variance prior to kickoff.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from src.config.logging_config import get_logger
from src.differential.evaluation import evaluate_per_gameweek
from src.differential.models import DifferentialMetrics

logger = get_logger(__name__)


@dataclass
class CeilingAnalysisResult:
    """Comparison of baseline, learned model, and oracle information bounds."""
    baseline_prauc: float
    model_prauc: float
    oracle_minutes_prauc: float
    oracle_full_prauc: float
    minutes_information_gain: float
    full_oracle_information_gain: float
    summary_report: str


def run_information_ceiling_analysis(
    test_df: pd.DataFrame,
    model_score_col: str,
    baseline_score_col: str = "score_baseline_e",
    target_col: str = "total_points",
    threshold: int = 8,
) -> CeilingAnalysisResult:
    """Measure the predictive gap between pre-GW model and post-kickoff oracles.

    Args:
        test_df: Evaluation split containing both pre-GW features and actual match stats.
        model_score_col: Column with learned model scores.
        baseline_score_col: Column with baseline scores.
        target_col: Outcome column.
        threshold: Score threshold (default 8).

    Returns:
        CeilingAnalysisResult with comparative metrics and gap quantification.
    """
    logger.info("Running Information Ceiling Diagnostic Analysis...")

    df = test_df.copy()
    y_actual = pd.to_numeric(df[target_col], errors="coerce").fillna(0).values
    y_bin = (y_actual >= threshold).astype(int)

    # 1. Baseline PR-AUC
    base_scores = pd.to_numeric(df.get(baseline_score_col, 0.0), errors="coerce").fillna(0).values
    base_prauc = float(average_precision_score(y_bin, base_scores)) if y_bin.sum() > 0 else 0.0

    # 2. Learned Pre-GW Model PR-AUC
    mod_scores = pd.to_numeric(df[model_score_col], errors="coerce").fillna(0).values
    mod_prauc = float(average_precision_score(y_bin, mod_scores)) if y_bin.sum() > 0 else 0.0

    # 3. Oracle A: Knows exact same-GW minutes played
    # Score = pre_gw_form * (same_gw_minutes / 90)
    minutes_actual = pd.to_numeric(df.get("minutes", 0.0), errors="coerce").fillna(0).values
    oracle_min_score = mod_scores * (minutes_actual / 90.0)
    oracle_min_prauc = float(average_precision_score(y_bin, oracle_min_score)) if y_bin.sum() > 0 else 0.0

    # 4. Oracle B: Knows same-GW xG, xA, and minutes (offensive chance creation)
    xg_actual = pd.to_numeric(df.get("expected_goals", 0.0), errors="coerce").fillna(0).values
    xa_actual = pd.to_numeric(df.get("expected_assists", 0.0), errors="coerce").fillna(0).values
    oracle_full_score = (xg_actual * 5.0 + xa_actual * 3.0 + minutes_actual / 90.0 * 2.0)
    oracle_full_prauc = float(average_precision_score(y_bin, oracle_full_score)) if y_bin.sum() > 0 else 0.0

    min_gain = oracle_min_prauc - mod_prauc
    full_gain = oracle_full_prauc - mod_prauc

    report = (
        "### Information Ceiling Diagnostic Summary\n\n"
        f"- **Baseline (Pre-GW):** PR-AUC = {base_prauc:.4f}\n"
        f"- **Learned Model (Pre-GW):** PR-AUC = {mod_prauc:.4f}\n"
        f"- **Oracle A (Knows exact minutes played):** PR-AUC = {oracle_min_prauc:.4f} (+{min_gain:.4f})\n"
        f"- **Oracle B (Knows actual chances created):** PR-AUC = {oracle_full_prauc:.4f} (+{full_gain:.4f})\n\n"
        f"**Interpretation:** Playing time uncertainty accounts for {min_gain / max(full_gain, 1e-5) * 100:.1f}% "
        "of the predictability ceiling gap before match kickoff."
    )

    logger.info("Information Ceiling: Base=%.4f, Model=%.4f, OracleMin=%.4f, OracleFull=%.4f",
                base_prauc, mod_prauc, oracle_min_prauc, oracle_full_prauc)

    return CeilingAnalysisResult(
        baseline_prauc=round(base_prauc, 4),
        model_prauc=round(mod_prauc, 4),
        oracle_minutes_prauc=round(oracle_min_prauc, 4),
        oracle_full_prauc=round(oracle_full_prauc, 4),
        minutes_information_gain=round(min_gain, 4),
        full_oracle_information_gain=round(full_gain, 4),
        summary_report=report,
    )
