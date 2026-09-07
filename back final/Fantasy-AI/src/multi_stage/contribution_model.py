"""Player Contribution Prediction Model.

Predicts individual player contributions: expected_goals, expected_assists,
clean_sheet_probability. Benchmarks separate-per-target vs multi-output
approaches and selects the best for each target independently.

Uses GW-level expanding walk-forward to generate leakage-safe OOF
predictions that become downstream features for the Points model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import joblib

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger
from src.multi_stage.temporal_cv import (
    generate_walk_forward_folds,
)
from src.multi_stage.model_selection import (
    build_contribution_candidates,
    select_best_model,
)

logger = get_logger(__name__)

# Contribution targets and their characteristics
CONTRIBUTION_TARGETS = {
    "goals_scored": {
        "output_name": "contrib_predicted_goals",
        "metric": "mae",
        "type": "regression",
    },
    "assists": {
        "output_name": "contrib_predicted_assists",
        "metric": "mae",
        "type": "regression",
    },
    "clean_sheets": {
        "output_name": "contrib_clean_sheet_probability",
        "metric": "mae",
        "type": "regression",  # treat as regression on 0/1 target
    },
}

# Feature columns for contribution prediction
# These should be pre-match features (rolling/lagged, never same-GW leakage)
CONTRIBUTION_FEATURE_PREFIXES = [
    "total_points_avg_last_",
    "minutes_avg_last_",
    "bps_avg_last_",
    "ict_index_avg_last_",
    "xG_avg_last_",
    "xA_avg_last_",
    "threat_avg_last_",
    "creativity_avg_last_",
    "influence_avg_last_",
    "goals_scored_avg_last_",
    "assists_avg_last_",
    "bonus_avg_last_",
    "key_passes_avg_last_",
    "big_chances_created_avg_last_",
    "big_chances_missed_avg_last_",
]

CONTRIBUTION_FEATURE_EXACT = [
    "form_index",
    "expected_minutes",
    "is_home",
    "team_strength",
    "opponent_strength",
    "fixture_difficulty",
    "clean_sheet_likelihood",
    "team_attack_strength",
    "team_defence_strength",
    "opponent_attack_strength",
    "opponent_defence_strength",
    "rest_days",
    "rotation_risk_index",
    "consecutive_starts",
    "prev_gw_minutes",
    "prev_gw_played",
    "minutes_share_last_5",
    "minutes_std_last_5",
    "opportunity_index",
    "attacking_contribution",
    "position_DEF",
    "position_FWD",
    "position_GK",
    "position_GKP",
    "position_MID",
    "team_is_promoted",
    "opponent_is_promoted",
    "is_newly_promoted_player",
    "value",
    "GW",
    # Match prediction features (from upstream match model)
    "match_predicted_team_goals",
    "match_predicted_opponent_goals",
    "match_predicted_win_prob",
    "match_predicted_draw_prob",
    "match_predicted_loss_prob",
    "match_predicted_goal_difference",
    "match_difficulty",
]


def _get_contribution_features(df: pd.DataFrame) -> list[str]:
    """Identify available contribution model features in the DataFrame."""
    features = []

    # Prefix-based features
    for prefix in CONTRIBUTION_FEATURE_PREFIXES:
        for col in df.columns:
            if col.startswith(prefix) and pd.api.types.is_numeric_dtype(df[col]):
                features.append(col)

    # Exact features
    for col in CONTRIBUTION_FEATURE_EXACT:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            features.append(col)

    # Deduplicate while preserving order
    seen = set()
    unique_features = []
    for f in features:
        if f not in seen:
            seen.add(f)
            unique_features.append(f)

    return unique_features


@dataclass
class ContributionTargetResult:
    """Result for a single contribution target."""
    target: str
    output_name: str
    best_model_name: str = ""
    best_model: object = None
    feature_cols: list[str] = field(default_factory=list)
    all_metrics: dict = field(default_factory=dict)
    val_mae: float = float("inf")
    val_brier: float = float("inf")


@dataclass
class ContributionModelResult:
    """Combined result for all contribution targets."""
    target_results: dict[str, ContributionTargetResult] = field(default_factory=dict)
    oof_predictions: pd.DataFrame = field(default_factory=pd.DataFrame)
    feature_cols: list[str] = field(default_factory=list)


def train_contribution_model(
    df: pd.DataFrame,
    min_train_gameweeks: int = 38,
    random_state: int = 42,
    match_oof_cols: list[str] | None = None,
    fold_step: int = 5,
) -> ContributionModelResult:
    """Train contribution prediction models with walk-forward validation.

    Trains a separate model per target and selects the best algorithm
    for each independently. Generates OOF predictions for downstream use.

    Args:
        df: Full player-level dataset with features and match predictions.
        min_train_gameweeks: Minimum GWs before first prediction fold.
        random_state: Random seed.
        match_oof_cols: List of match OOF columns present in df
            (used as features for contribution model).
        fold_step: Number of consecutive GWs to batch per model training.

    Returns:
        ContributionModelResult with per-target models and OOF predictions.
    """
    logger.info("Training contribution models (fold_step=%d)...", fold_step)

    feature_cols = _get_contribution_features(df)
    if not feature_cols:
        logger.warning("No contribution features available.")
        return ContributionModelResult()

    logger.info("Contribution features (%d): %s", len(feature_cols), feature_cols[:20])

    # Generate walk-forward folds with fold_step
    folds = generate_walk_forward_folds(
        df, min_train_gameweeks, season_col="season", gw_col="GW", fold_step=fold_step
    )
    if not folds:
        logger.warning("No walk-forward folds for contribution model.")
        return ContributionModelResult()

    # Validation folds for model selection
    n_val_folds = max(1, len(folds) // 5)
    val_folds = folds[-n_val_folds:]

    result = ContributionModelResult(
        oof_predictions=df.copy(),
        feature_cols=feature_cols,
    )

    # Train each target independently
    for target_name, target_config in CONTRIBUTION_TARGETS.items():
        if target_name not in df.columns:
            logger.warning("Target '%s' not found in data — skipping.", target_name)
            continue

        output_name = target_config["output_name"]
        metric = target_config["metric"]

        logger.info("Training contribution model for '%s'...", target_name)

        target_result = _train_single_contribution_target(
            df=df,
            feature_cols=feature_cols,
            target_col=target_name,
            output_name=output_name,
            folds=folds,
            val_folds=val_folds,
            metric=metric,
            random_state=random_state,
        )

        result.target_results[target_name] = target_result

        # Store OOF predictions
        if f"oof_{target_name}" in result.oof_predictions.columns:
            result.oof_predictions[output_name] = result.oof_predictions[f"oof_{target_name}"]
        else:
            result.oof_predictions[output_name] = np.nan

    return result


def _train_single_contribution_target(
    df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    output_name: str,
    folds: list,
    val_folds: list,
    metric: str,
    random_state: int,
) -> ContributionTargetResult:
    """Train and select best model for a single contribution target."""
    # Prepare data for model selection
    available_features = [c for c in feature_cols if c in df.columns]

    # Build validation sets from the validation folds
    val_train_mask = np.zeros(len(df), dtype=bool)
    val_pred_mask = np.zeros(len(df), dtype=bool)

    if len(folds) > len(val_folds):
        for f in folds[:-len(val_folds)]:
            val_train_mask |= f.train_mask | f.predict_mask
        for f in val_folds:
            val_pred_mask |= f.predict_mask
    else:
        # Fallback: simple split
        split_idx = int(len(df) * 0.8)
        val_train_mask[:split_idx] = True
        val_pred_mask[split_idx:] = True

    train_data = df.loc[val_train_mask]
    val_data = df.loc[val_pred_mask]

    X_train = train_data[available_features].apply(pd.to_numeric, errors="coerce").fillna(0)
    y_train = pd.to_numeric(train_data[target_col], errors="coerce")
    X_val = val_data[available_features].apply(pd.to_numeric, errors="coerce").fillna(0)
    y_val = pd.to_numeric(val_data[target_col], errors="coerce")

    valid_train = y_train.notna()
    valid_val = y_val.notna()

    if valid_train.sum() < 50 or valid_val.sum() < 20:
        logger.warning("Insufficient data for target '%s'.", target_col)
        return ContributionTargetResult(
            target=target_col, output_name=output_name,
        )

    # Select best model
    candidates = build_contribution_candidates(target_col, random_state)
    logger.info("Selecting best model for '%s' from %d candidates...", target_col, len(candidates))

    try:
        best_name, best_model, all_metrics = select_best_model(
            candidates,
            X_train.loc[valid_train], y_train.loc[valid_train],
            X_val.loc[valid_val], y_val.loc[valid_val],
            metric=metric,
        )
    except RuntimeError as exc:
        logger.error("Model selection failed for '%s': %s", target_col, exc)
        return ContributionTargetResult(
            target=target_col, output_name=output_name,
        )

    # Generate OOF predictions using walk-forward with the best algorithm
    oof_col = f"oof_{target_col}"
    oof_preds = pd.Series(np.nan, index=df.index, name=oof_col)

    best_builder = None
    for name, builder in candidates:
        if name == best_name:
            best_builder = builder
            break

    if best_builder is None:
        best_builder = candidates[0][1]

    model_cache: dict[int, tuple] = {}
    for fold in folds:
        cache_key = fold.train_temporal_max

        if cache_key not in model_cache:
            fold_train = df.loc[fold.train_mask]
            X_tr = fold_train[available_features].apply(pd.to_numeric, errors="coerce")
            y_tr = pd.to_numeric(fold_train[target_col], errors="coerce")
            valid = y_tr.notna()
            if valid.sum() < 10:
                model_cache[cache_key] = (None, None)
                continue

            tr_medians = X_tr.loc[valid].median()
            X_tr = X_tr.loc[valid].fillna(tr_medians).fillna(0)

            try:
                model = best_builder()
                model.fit(X_tr, y_tr.loc[valid])
                model_cache[cache_key] = (model, tr_medians)
            except Exception as exc:
                logger.warning(
                    "Contribution fold %d for '%s' failed: %s",
                    fold.fold_id, target_col, exc,
                )
                model_cache[cache_key] = (None, None)
                continue

        cached_model, cached_medians = model_cache[cache_key]
        if cached_model is None:
            continue

        fold_pred = df.loc[fold.predict_mask]
        X_pr = fold_pred[available_features].apply(pd.to_numeric, errors="coerce")
        X_pr = X_pr.fillna(cached_medians).fillna(0)
        if X_pr.empty:
            continue

        try:
            preds = cached_model.predict(X_pr)
            oof_preds.loc[fold.predict_mask] = preds
        except Exception as exc:
            logger.warning(
                "Contribution fold %d for '%s' predict failed: %s",
                fold.fold_id, target_col, exc,
            )

    # Store OOF in the result DataFrame — we need to update the
    # caller's oof_predictions via the column name
    # The caller will read this from the result
    n_pred = oof_preds.notna().sum()

    val_mae = all_metrics.get(best_name, {}).get("mae", float("inf"))

    logger.info(
        "Contribution '%s': best=%s, MAE=%.4f, OOF=%d/%d rows.",
        target_col, best_name, val_mae, n_pred, len(df),
    )

    target_result = ContributionTargetResult(
        target=target_col,
        output_name=output_name,
        best_model_name=best_name,
        best_model=best_model,
        feature_cols=available_features,
        all_metrics=all_metrics,
        val_mae=val_mae,
    )

    # Also put oof preds back into the df copy (handled by caller via col name)
    # Store as attribute
    target_result._oof_preds = oof_preds

    return target_result


# -----------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------

def save_contribution_models(
    result: ContributionModelResult,
    output_dir: Path,
) -> None:
    """Save contribution models and metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for target_name, target_result in result.target_results.items():
        if target_result.best_model is not None:
            model_path = output_dir / f"contrib_{target_name}_model.joblib"
            joblib.dump(target_result.best_model, model_path)
            logger.info("Saved contribution model '%s' to %s.", target_name, model_path)

    metadata = {
        target_name: {
            "best_model_name": tr.best_model_name,
            "output_name": tr.output_name,
            "feature_cols": tr.feature_cols,
            "all_metrics": tr.all_metrics,
            "val_mae": tr.val_mae,
        }
        for target_name, tr in result.target_results.items()
    }
    metadata["feature_cols"] = result.feature_cols

    meta_path = output_dir / "contribution_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    logger.info("Saved contribution metadata to %s.", meta_path)


def load_contribution_models(model_dir: Path) -> dict[str, tuple[object, dict]]:
    """Load saved contribution models and metadata."""
    meta_path = model_dir / "contribution_metadata.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}

    models = {}
    for target_name in CONTRIBUTION_TARGETS:
        model_path = model_dir / f"contrib_{target_name}_model.joblib"
        if model_path.exists():
            models[target_name] = (joblib.load(model_path), metadata.get(target_name, {}))

    return models
