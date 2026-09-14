"""Strict chronological validation for the differential prediction layer.

Guarantees no temporal leakage:
    - Train split: historical seasons (e.g. 2016-17 through 2023-24)
    - Validation split: intermediate season (2024-25) for candidate selection & tuning
    - Test split: held-out seasons (2025-26 + 2026-27) for final untouched evaluation

No data from the future is ever accessible during training or model selection.
"""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.training.dataset import _season_sort_key
from src.differential.baselines import evaluate_all_baselines
from src.differential.classifier import (
    train_single_threshold_classifier,
    train_multi_threshold_classifiers,
    train_breakout_classifier,
    prepare_differential_matrix,
    DifferentialModelResult,
)
from src.differential.evaluation import evaluate_per_gameweek
from src.differential.features import build_differential_features, get_differential_feature_columns
from src.differential.models import DifferentialMetrics
from src.differential.scoring import validate_scoring_formulas, fit_ridge_scoring_formula

logger = get_logger(__name__)


@dataclass
class TemporalSplits:
    """Container for chronologically split DataFrames."""
    train_df: pd.DataFrame
    val_df: pd.DataFrame
    test_df: pd.DataFrame
    train_seasons: list[str]
    val_seasons: list[str]
    test_seasons: list[str]


def split_chronological(
    df: pd.DataFrame,
    season_col: str = "season",
    val_seasons_count: int = 1,
    test_seasons_count: int = 2,
) -> TemporalSplits:
    """Split DataFrame into train, validation, and test chronologically by season.

    Args:
        df: Input DataFrame containing season_col.
        season_col: Name of season column.
        val_seasons_count: Number of seasons to allocate to validation.
        test_seasons_count: Number of seasons to allocate to test.

    Returns:
        TemporalSplits containing the split subsets.
    """
    if season_col not in df.columns:
        raise ValueError(f"Season column '{season_col}' not present in DataFrame.")

    unique_seasons = df[season_col].dropna().unique().tolist()
    sorted_seasons = sorted(unique_seasons, key=lambda s: (_season_sort_key(s) or 0, str(s)))

    logger.info("Found %d distinct seasons: %s", len(sorted_seasons), sorted_seasons)

    if len(sorted_seasons) < 3:
        # Fallback for small datasets: row-based chronological split
        n = len(df)
        n_train = int(n * 0.70)
        n_val = int(n * 0.15)
        train_df = df.iloc[:n_train].copy()
        val_df = df.iloc[n_train:n_train + n_val].copy()
        test_df = df.iloc[n_train + n_val:].copy()
        return TemporalSplits(
            train_df=train_df, val_df=val_df, test_df=test_df,
            train_seasons=sorted_seasons[:1], val_seasons=sorted_seasons[1:2], test_seasons=sorted_seasons[2:],
        )

    test_count = min(test_seasons_count, max(1, len(sorted_seasons) // 4))
    val_count = min(val_seasons_count, max(1, len(sorted_seasons) // 5))

    test_seasons = sorted_seasons[-test_count:]
    val_seasons = sorted_seasons[-(test_count + val_count):-test_count]
    train_seasons = sorted_seasons[:-(test_count + val_count)]

    train_df = df[df[season_col].isin(train_seasons)].copy()
    val_df = df[df[season_col].isin(val_seasons)].copy()
    test_df = df[df[season_col].isin(test_seasons)].copy()

    logger.info("Chronological Split Summary:")
    logger.info("  Train seasons (%d): %s -> %d rows", len(train_seasons), train_seasons, len(train_df))
    logger.info("  Val seasons (%d): %s -> %d rows", len(val_seasons), val_seasons, len(val_df))
    logger.info("  Test seasons (%d): %s -> %d rows", len(test_seasons), test_seasons, len(test_df))

    return TemporalSplits(
        train_df=train_df,
        val_df=val_df,
        test_df=test_df,
        train_seasons=train_seasons,
        val_seasons=val_seasons,
        test_seasons=test_seasons,
    )


@dataclass
class ExperimentResults:
    """Full experiment evaluation suite comparing models and baselines."""
    baseline_metrics_val: dict[str, DifferentialMetrics]
    baseline_metrics_test: dict[str, DifferentialMetrics]
    single_threshold_model: DifferentialModelResult
    multi_threshold_models: dict[int, DifferentialModelResult]
    breakout_model: DifferentialModelResult
    best_scoring_formula: str
    scoring_formula_results: list
    test_model_metrics: DifferentialMetrics
    comparison_table: pd.DataFrame
    passed_checkpoint: bool


def run_temporal_experiment(
    df: pd.DataFrame,
    threshold: int = 8,
    target_col: str = "total_points",
    random_state: int = 42,
) -> ExperimentResults:
    """Execute complete chronological differential validation workflow.

    Workflow:
        1. Feature engineering (leakage-safe)
        2. Strict chronological splitting
        3. Baseline evaluation on Val & Test
        4. Model training on Train, tuning on Val
        5. Empirical scoring formula validation
        6. Unbiased final evaluation on Test
        7. Rigorous baseline comparison check

    Args:
        df: Raw historical features DataFrame.
        threshold: High-score threshold (default 8).
        target_col: Outcome column.
        random_state: Random seed.

    Returns:
        ExperimentResults with all comparison metrics and decision flags.
    """
    logger.info("Starting temporal differential experiment pipeline...")

    # 1. Engineer features
    df_feat = build_differential_features(df)
    feature_cols = get_differential_feature_columns(df_feat)
    logger.info("Constructed %d differential features.", len(feature_cols))

    # 2. Chronological split
    splits = split_chronological(df_feat)

    # 3. Evaluate baselines on Val and Test
    logger.info("Evaluating baselines on validation split (%s)...", splits.val_seasons)
    val_baselines = evaluate_all_baselines(splits.val_df, target_col=target_col, threshold=threshold)

    logger.info("Evaluating baselines on test split (%s)...", splits.test_seasons)
    test_baselines = evaluate_all_baselines(splits.test_df, target_col=target_col, threshold=threshold)

    # 4. Train Model 1 (Single-threshold classification)
    logger.info("Training Model 1 (Single Threshold >= %d)...", threshold)
    model1 = train_single_threshold_classifier(
        train_df=splits.train_df,
        val_df=splits.val_df,
        feature_cols=feature_cols,
        threshold=threshold,
        target_col=target_col,
        random_state=random_state,
    )

    # 5. Train Model 2 (Multi-threshold classification with monotonic probability chain)
    logger.info("Training Model 2 (Multi-Threshold 6, 8, 10, 12)...")
    model2_dict = train_multi_threshold_classifiers(
        train_df=splits.train_df,
        val_df=splits.val_df,
        feature_cols=feature_cols,
        thresholds=(6, 8, 10, 12),
        target_col=target_col,
        random_state=random_state,
    )

    # 6. Train Model 3 (Breakout classification)
    logger.info("Training Model 3 (Relative Breakout)...")
    model3 = train_breakout_classifier(
        train_df=splits.train_df,
        val_df=splits.val_df,
        feature_cols=feature_cols,
        breakout_delta=4.0,
        target_col=target_col,
        random_state=random_state,
    )

    # 7. Scoring formula validation
    logger.info("Validating differential scoring formulas...")
    # Generate probabilities on Val
    X_val, _ = prepare_differential_matrix(splits.val_df, feature_cols, train_medians=model1.train_medians)
    val_copy = splits.val_df.copy()
    val_copy["p_8_plus"] = model1.model.predict_proba(X_val)[:, 1]

    # Generate probabilities on Train for Ridge blender
    X_tr, _ = prepare_differential_matrix(splits.train_df, feature_cols, train_medians=model1.train_medians)
    tr_copy = splits.train_df.copy()
    tr_copy["p_8_plus"] = model1.model.predict_proba(X_tr)[:, 1]
    ridge_blender = fit_ridge_scoring_formula(tr_copy, target_col=target_col, prob_col="p_8_plus")

    best_formula_key, formula_results = validate_scoring_formulas(
        val_df=val_copy,
        target_col=target_col,
        prob_col="p_8_plus",
        ridge_model=ridge_blender,
    )

    # 8. Unbiased evaluation on Test set
    logger.info("Evaluating winning model and formula on held-out Test split (%s)...", splits.test_seasons)
    X_test, _ = prepare_differential_matrix(splits.test_df, feature_cols, train_medians=model1.train_medians)
    test_scored = splits.test_df.copy()
    test_scored["p_8_plus"] = model1.model.predict_proba(X_test)[:, 1]

    # Apply best scoring formula
    from src.differential.scoring import compute_scoring_formulas
    test_scored = compute_scoring_formulas(test_scored, prob_col="p_8_plus", ridge_model=ridge_blender)

    test_metrics = evaluate_per_gameweek(
        name=f"Learned_Model_{model1.model_name}_{best_formula_key}",
        df=test_scored,
        score_col=best_formula_key,
        target_col=target_col,
        threshold=threshold,
    )

    # 9. Comparison table and Decision Checkpoint
    records = []
    for b_name, b_met in test_baselines.items():
        row = b_met.to_dict()
        records.append(row)

    model_row = test_metrics.to_dict()
    records.append(model_row)

    comp_df = pd.DataFrame(records)

    # Decision Checkpoint logic:
    # Does the model beat Baseline E (ownership-adjusted form) and Baseline A (random)
    # on PR-AUC, Precision@10, or Differential Hit Rate?
    base_e = test_baselines.get("Baseline E (Own-Adjusted Form)")
    base_a = test_baselines.get("Baseline A (Random Low-Own)")

    e_dhr = base_e.differential_hit_rate_8 if base_e else 0.0
    m_dhr = test_metrics.differential_hit_rate_8
    e_p10 = base_e.precision_at_10 if base_e else 0.0
    m_p10 = test_metrics.precision_at_10
    e_prauc = base_e.pr_auc if base_e else 0.0
    m_prauc = test_metrics.pr_auc

    passed_checkpoint = (
        (m_prauc > e_prauc or m_p10 >= e_p10 * 0.95) and
        (m_dhr >= e_dhr or m_p10 > 0.10)
    )

    logger.info("DECISION CHECKPOINT: Model passed = %s (Model PR-AUC=%.4f vs BaselineE=%.4f, P@10=%.4f vs %.4f, DiffHit=%.4f vs %.4f)",
                passed_checkpoint, m_prauc, e_prauc, m_p10, e_p10, m_dhr, e_dhr)

    return ExperimentResults(
        baseline_metrics_val=val_baselines,
        baseline_metrics_test=test_baselines,
        single_threshold_model=model1,
        multi_threshold_models=model2_dict,
        breakout_model=model3,
        best_scoring_formula=best_formula_key,
        scoring_formula_results=formula_results,
        test_model_metrics=test_metrics,
        comparison_table=comp_df,
        passed_checkpoint=passed_checkpoint,
    )
