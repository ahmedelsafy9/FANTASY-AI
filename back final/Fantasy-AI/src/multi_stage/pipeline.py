"""Recursively leakage-safe multi-stage prediction pipeline.

Orchestrates the three prediction stages (Match → Contribution → Points)
ensuring that at every historical fold t:
  - Match model is trained only on data before t
  - Contribution model is trained only on data before t, receiving
    match predictions generated without seeing t
  - Points model trains on OOF features that realistically simulate
    inference-time noise

Also provides inference-time prediction for the next unplayed GW.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import time

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.multi_stage.match_model import (
    MatchModelResult,
    build_match_dataset,
    train_match_model,
    map_match_predictions_to_players,
    save_match_model,
)
from src.multi_stage.contribution_model import (
    ContributionModelResult,
    CONTRIBUTION_TARGETS,
    train_contribution_model,
    save_contribution_models,
    _get_contribution_features,
)
from src.multi_stage.temporal_cv import (
    generate_walk_forward_folds,
    make_temporal_index,
)
from src.multi_stage.model_selection import (
    build_points_candidates,
    select_best_model,
)

logger = get_logger(__name__)


@dataclass
class MultiStageResult:
    """Complete result of the multi-stage pipeline.

    Attributes:
        match_result: Match model training result.
        contribution_result: Contribution model training result.
        points_model_name: Best points model name.
        points_model: Fitted points model.
        points_feature_cols: Feature columns for the points model.
        points_metrics: Points model validation metrics.
        ablation_results: Ablation study results comparing configurations.
        augmented_data: Full dataset with all OOF predictions added.
        train_medians: Per-feature medians from training data for inference.
    """
    match_result: MatchModelResult = field(default_factory=MatchModelResult)
    contribution_result: ContributionModelResult = field(default_factory=ContributionModelResult)
    points_model_name: str = ""
    points_model: object = None
    points_feature_cols: list[str] = field(default_factory=list)
    points_metrics: dict = field(default_factory=dict)
    ablation_results: dict = field(default_factory=dict)
    augmented_data: pd.DataFrame = field(default_factory=pd.DataFrame)
    train_medians: dict = field(default_factory=dict)


# -----------------------------------------------------------------------
# Feature column definitions for each ablation configuration
# -----------------------------------------------------------------------

MATCH_PREDICTION_COLS = [
    "match_predicted_team_goals",
    "match_predicted_opponent_goals",
    "match_predicted_win_prob",
    "match_predicted_draw_prob",
    "match_predicted_loss_prob",
    "match_predicted_goal_difference",
    "match_difficulty",
]

CONTRIBUTION_PREDICTION_COLS = [
    "contrib_predicted_goals",
    "contrib_predicted_assists",
    "contrib_clean_sheet_probability",
]


def _get_baseline_feature_cols(df: pd.DataFrame, settings=None) -> list[str]:
    """Get the Feedback 3 baseline feature columns (excluding multi-stage predictions)."""
    from src.training.dataset import select_feature_columns
    from src.config.settings import TrainingSettings

    if settings is None:
        settings = TrainingSettings()

    # Get all feature columns, then remove multi-stage prediction columns
    all_features = select_feature_columns(df, settings)
    exclude = set(MATCH_PREDICTION_COLS + CONTRIBUTION_PREDICTION_COLS)
    return [c for c in all_features if c not in exclude]


def run_multi_stage_pipeline(
    df: pd.DataFrame,
    min_train_gameweeks: int = 38,
    random_state: int = 42,
    fold_step: int = 5,
) -> MultiStageResult:
    """Run the complete multi-stage prediction pipeline.

    Stages:
    1. Train match model → generate OOF match predictions
    2. Augment player data with match predictions
    3. Train contribution model → generate OOF contribution predictions
    4. Augment player data with contribution predictions
    5. Train points model with augmented features
    6. Run ablation study comparing configurations

    All stages use GW-level expanding walk-forward cross-validation.

    Args:
        df: Full player-level engineered dataset.
        min_train_gameweeks: Minimum GWs before first prediction fold.
        random_state: Random seed.
        fold_step: Number of consecutive GWs to batch per model training.

    Returns:
        MultiStageResult with all models, OOF predictions, and ablation results.
    """
    logger.info("=" * 60)
    logger.info("STARTING MULTI-STAGE PREDICTION PIPELINE (fold_step=%d)", fold_step)
    logger.info("=" * 60)
    start_time = time.perf_counter()

    result = MultiStageResult()

    # ------------------------------------------------------------------
    # Stage 1: Match Model
    # ------------------------------------------------------------------
    logger.info("-" * 60)
    logger.info("STAGE 1: Match Result Prediction")
    logger.info("-" * 60)

    match_result = train_match_model(
        df, min_train_gameweeks=min_train_gameweeks, random_state=random_state,
        fold_step=1,
    )
    result.match_result = match_result

    # Map match OOF predictions to player level
    augmented = map_match_predictions_to_players(
        df, match_result.oof_predictions
    )

    logger.info(
        "Stage 1 complete: match model=%s, OOF coverage=%.1f%%.",
        match_result.best_model_name,
        100 * augmented["match_predicted_team_goals"].notna().sum() / max(len(augmented), 1),
    )

    # ------------------------------------------------------------------
    # Stage 2: Contribution Model
    # ------------------------------------------------------------------
    logger.info("-" * 60)
    logger.info("STAGE 2: Player Contribution Prediction")
    logger.info("-" * 60)

    contribution_result = train_contribution_model(
        augmented,
        min_train_gameweeks=min_train_gameweeks,
        random_state=random_state,
        fold_step=fold_step,
    )
    result.contribution_result = contribution_result

    # Add OOF contribution predictions to augmented data
    for target_name, target_result in contribution_result.target_results.items():
        oof_col = CONTRIBUTION_TARGETS[target_name]["output_name"]
        if hasattr(target_result, '_oof_preds'):
            augmented[oof_col] = target_result._oof_preds.values
        elif oof_col in contribution_result.oof_predictions.columns:
            augmented[oof_col] = contribution_result.oof_predictions[oof_col].values

    logger.info("Stage 2 complete: %d contribution targets trained.", len(contribution_result.target_results))

    result.augmented_data = augmented

    # ------------------------------------------------------------------
    # Stage 3: Points Model with Ablation Study
    # ------------------------------------------------------------------
    logger.info("-" * 60)
    logger.info("STAGE 3: FPL Points Prediction + Ablation Study")
    logger.info("-" * 60)

    ablation_results, best_config, points_model, points_features, points_metrics, train_medians = (
        _run_ablation_study(
            augmented,
            min_train_gameweeks=min_train_gameweeks,
            random_state=random_state,
        )
    )

    result.ablation_results = ablation_results
    result.points_model_name = best_config
    result.points_model = points_model
    result.points_feature_cols = points_features
    result.points_metrics = points_metrics
    result.train_medians = train_medians

    total_time = time.perf_counter() - start_time
    logger.info("=" * 60)
    logger.info(
        "MULTI-STAGE PIPELINE COMPLETE in %.1fs. Best config: %s",
        total_time, best_config,
    )
    logger.info("=" * 60)

    return result


def _run_ablation_study(
    df: pd.DataFrame,
    min_train_gameweeks: int = 38,
    random_state: int = 42,
) -> tuple[dict, str, object, list[str], dict, dict]:
    """Run the mandatory ablation study.

    Compares four configurations on identical out-of-time windows:
      A) Baseline (Feedback 3 features only)
      B) Baseline + Match Predictions
      C) Baseline + Contribution Predictions
      D) Baseline + Match + Contribution Predictions

    Returns:
        Tuple of (ablation_results, best_config_name, best_model,
                  best_feature_cols, best_metrics, train_medians).
    """
    from src.config.settings import TrainingSettings
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from scipy.stats import spearmanr

    settings = TrainingSettings()
    baseline_features = _get_baseline_feature_cols(df, settings)

    # Define the four configurations
    configs = {
        "A_baseline": baseline_features,
        "B_plus_match": baseline_features + [
            c for c in MATCH_PREDICTION_COLS if c in df.columns
        ],
        "C_plus_contrib": baseline_features + [
            c for c in CONTRIBUTION_PREDICTION_COLS if c in df.columns
        ],
        "D_full": baseline_features + [
            c for c in MATCH_PREDICTION_COLS + CONTRIBUTION_PREDICTION_COLS
            if c in df.columns
        ],
    }

    # Chronological train/test split (same for all configs)
    target_col = settings.target_column
    if target_col not in df.columns:
        logger.error("Target column '%s' not found.", target_col)
        return {}, "A_baseline", None, baseline_features, {}, {}

    working = df.dropna(subset=[target_col]).copy()
    working = working.sort_values(["season", "GW"]).reset_index(drop=True)

    split_idx = int(len(working) * (1 - settings.test_fraction))
    split_idx = max(1, min(split_idx, len(working) - 1))

    train_df = working.iloc[:split_idx]
    test_df = working.iloc[split_idx:]

    y_test = pd.to_numeric(test_df[target_col], errors="coerce")

    ablation_results = {}
    best_config = "A_baseline"
    best_score = float("inf")
    best_model = None
    best_features = baseline_features
    best_metrics_all = {}
    best_medians = {}

    for config_name, feature_cols in configs.items():
        logger.info("Ablation: evaluating config '%s' with %d features...", config_name, len(feature_cols))

        available = [c for c in feature_cols if c in working.columns]
        if not available:
            logger.warning("Config '%s' has no available features — skipping.", config_name)
            continue

        X_train = train_df[available].apply(pd.to_numeric, errors="coerce")
        X_test = test_df[available].apply(pd.to_numeric, errors="coerce")
        y_train = pd.to_numeric(train_df[target_col], errors="coerce")

        # Impute using training medians
        train_medians = X_train.median().to_dict()
        X_train = X_train.fillna(train_medians).fillna(0)
        X_test = X_test.fillna(train_medians).fillna(0)

        valid_train = y_train.notna()
        valid_test = y_test.notna()

        if valid_train.sum() < 100 or valid_test.sum() < 20:
            continue

        # Select best model for this configuration
        candidates = build_points_candidates(random_state)

        try:
            name, model, all_model_metrics = select_best_model(
                candidates,
                X_train.loc[valid_train], y_train.loc[valid_train],
                X_test.loc[valid_test], y_test.loc[valid_test],
                metric="mae",
            )
        except RuntimeError:
            logger.warning("Config '%s' failed model selection.", config_name)
            continue

        # Compute full metrics
        preds = model.predict(X_test.loc[valid_test])
        y_actual = y_test.loc[valid_test].values

        mae = float(mean_absolute_error(y_actual, preds))
        rmse = float(np.sqrt(mean_squared_error(y_actual, preds)))
        r2 = float(r2_score(y_actual, preds))

        sp_corr, _ = spearmanr(y_actual, preds)
        spearman = float(sp_corr) if np.isfinite(sp_corr) else 0.0

        # High-score metrics
        hs_metrics = _compute_high_score_metrics(y_actual, preds)

        config_metrics = {
            "model": name,
            "mae": mae,
            "rmse": rmse,
            "r2": r2,
            "spearman": spearman,
            "n_features": len(available),
            **hs_metrics,
            "per_model": all_model_metrics,
        }
        ablation_results[config_name] = config_metrics

        logger.info(
            "  Config '%s' [%s]: MAE=%.4f, RMSE=%.4f, R²=%.4f, Spearman=%.4f",
            config_name, name, mae, rmse, r2, spearman,
        )

        if mae < best_score:
            best_score = mae
            best_config = config_name
            best_model = model
            best_features = available
            best_metrics_all = config_metrics
            best_medians = {k: float(v) for k, v in train_medians.items() if pd.notna(v)}

    logger.info("Ablation study complete. Best config: '%s' (MAE=%.4f).", best_config, best_score)
    return ablation_results, best_config, best_model, best_features, best_metrics_all, best_medians


def _compute_high_score_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """Compute high-score detection metrics."""
    from src.training.ranking_metrics import high_score_recall, top_n_recall

    metrics = {}

    for threshold in [6, 8, 10, 12]:
        key = f"recall_{threshold}"
        try:
            metrics[key] = float(high_score_recall(y_true, y_pred, threshold=threshold, pred_threshold=threshold * 0.7))
        except Exception:
            metrics[key] = float("nan")

    for threshold in [6, 8, 10]:
        key = f"precision_{threshold}"
        try:
            pred_above = y_pred >= threshold * 0.7
            true_above = y_true >= threshold
            if pred_above.sum() > 0:
                metrics[key] = float(true_above[pred_above].mean())
            else:
                metrics[key] = float("nan")
        except Exception:
            metrics[key] = float("nan")

    try:
        metrics["top_20_recall"] = float(top_n_recall(y_true, y_pred, n=20))
    except Exception:
        metrics["top_20_recall"] = float("nan")

    return metrics


# -----------------------------------------------------------------------
# Inference: predict next gameweek
# -----------------------------------------------------------------------

def predict_next_gameweek(
    df: pd.DataFrame,
    pipeline_result: MultiStageResult,
    model_dir: Path | None = None,
) -> pd.DataFrame:
    """Predict the next unplayed GW using the multi-stage pipeline.

    Dynamically detects the next unplayed GW (never hardcoded).

    Flow:
    1. Auto-detect next unplayed GW
    2. Build next-GW feature rows (using existing logic)
    3. Run match model → match features
    4. Run contribution models → contribution features
    5. Run points model → predicted points

    Args:
        df: Full engineered dataset.
        pipeline_result: Result from run_multi_stage_pipeline.
        model_dir: Optional directory with saved models.

    Returns:
        pd.DataFrame: Player-level predictions for the next GW.
    """
    from src.prediction.next_gameweek import build_next_gameweek_rows
    from src.config.settings import get_settings

    settings = get_settings()

    # 1. Build next-GW rows using existing logic
    try:
        next_gw_rows = build_next_gameweek_rows(
            df,
            player_id_columns=settings.feature_engineering.player_id_columns,
            chronological_columns=settings.feature_engineering.chronological_columns,
            max_valid_gameweek=settings.prediction.max_valid_gameweek,
        )
    except Exception as exc:
        logger.error("Failed to build next-GW rows: %s", exc)
        return pd.DataFrame()

    target_gw = "unknown"
    if "predicted_for_gw" in next_gw_rows.columns:
        target_gw = int(next_gw_rows["predicted_for_gw"].mode().iloc[0]) if not next_gw_rows["predicted_for_gw"].isna().all() else "unknown"

    logger.info("Predicting for GW %s (%d players)...", target_gw, len(next_gw_rows))

    # 2. Generate match predictions for the next GW
    if pipeline_result.match_result.best_model is not None:
        match_model = pipeline_result.match_result.best_model
        match_features = pipeline_result.match_result.feature_cols

        # Build match-level features for next GW
        match_df = build_match_dataset(df)
        if not match_df.empty and match_features:
            # Get latest available features per team
            latest_team_features = (
                match_df.sort_values(["season", "GW"])
                .groupby("team").tail(1)
            )

            # Predict using available features
            available = [c for c in match_features if c in latest_team_features.columns]
            if available:
                X_match = latest_team_features[available].apply(pd.to_numeric, errors="coerce").fillna(0)
                try:
                    match_preds = match_model.predict(X_match)
                    latest_team_features["oof_goals_pred"] = match_preds

                    next_gw_rows = map_match_predictions_to_players(
                        next_gw_rows, latest_team_features,
                    )
                except Exception as exc:
                    logger.warning("Match model inference failed: %s", exc)
    else:
        # Fill match prediction columns with NaN
        for col in MATCH_PREDICTION_COLS:
            if col not in next_gw_rows.columns:
                next_gw_rows[col] = np.nan

    # 3. Generate contribution predictions for the next GW
    for target_name, target_result in pipeline_result.contribution_result.target_results.items():
        if target_result.best_model is not None:
            output_name = CONTRIBUTION_TARGETS[target_name]["output_name"]
            available = [c for c in target_result.feature_cols if c in next_gw_rows.columns]
            if available:
                X_contrib = next_gw_rows[available].apply(pd.to_numeric, errors="coerce").fillna(0)
                try:
                    preds = target_result.best_model.predict(X_contrib)
                    next_gw_rows[output_name] = preds
                except Exception as exc:
                    logger.warning("Contribution model '%s' inference failed: %s", target_name, exc)

    # Fill missing contribution columns
    for col in CONTRIBUTION_PREDICTION_COLS:
        if col not in next_gw_rows.columns:
            next_gw_rows[col] = np.nan

    # 4. Run points model
    if pipeline_result.points_model is not None:
        feature_cols = pipeline_result.points_feature_cols
        available = [c for c in feature_cols if c in next_gw_rows.columns]

        if available:
            X_points = next_gw_rows[available].apply(pd.to_numeric, errors="coerce")
            X_points = X_points.fillna(pipeline_result.train_medians).fillna(0)

            try:
                points_preds = pipeline_result.points_model.predict(X_points)
                next_gw_rows["predicted_total_points"] = points_preds
                next_gw_rows["predicted_expected_points"] = points_preds
            except Exception as exc:
                logger.error("Points model inference failed: %s", exc)
    else:
        logger.warning("No points model available for inference.")

    logger.info(
        "Next-GW prediction complete: %d players, target GW=%s.",
        len(next_gw_rows), target_gw,
    )
    return next_gw_rows


# -----------------------------------------------------------------------
# Save / Load
# -----------------------------------------------------------------------

def save_pipeline_result(result: MultiStageResult, output_dir: Path) -> None:
    """Save the complete pipeline result."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save match model
    save_match_model(result.match_result, output_dir)

    # Save contribution models
    save_contribution_models(result.contribution_result, output_dir)

    # Save points model
    if result.points_model is not None:
        import joblib
        points_path = output_dir / "points_model.joblib"
        joblib.dump(result.points_model, points_path)
        logger.info("Saved points model to %s.", points_path)

    # Save pipeline metadata
    metadata = {
        "points_model_name": result.points_model_name,
        "points_feature_cols": result.points_feature_cols,
        "points_metrics": result.points_metrics,
        "ablation_results": result.ablation_results,
        "train_medians": result.train_medians,
    }
    meta_path = output_dir / "pipeline_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    logger.info("Saved pipeline metadata to %s.", meta_path)
