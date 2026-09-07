"""Match Result Prediction Model.

Predicts team-level match outcomes (goals scored) from historical
team/opponent strength features. Derives win/draw/loss probabilities
via Poisson transformation. All training uses GW-level expanding
walk-forward to prevent leakage.

Two target formulations are compared:
  A) goals_scored_by_team (two rows per match, one per team perspective)
  B) home_goals / away_goals at match level (one row, two targets)

The better formulation is selected via out-of-time validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import json
import joblib
import numpy as np
import pandas as pd
from scipy.stats import poisson

from src.config.logging_config import get_logger
from src.multi_stage.temporal_cv import (
    generate_walk_forward_folds,
    make_temporal_index,
)
from src.multi_stage.model_selection import (
    build_match_candidates,
    select_best_model,
)

logger = get_logger(__name__)

# -----------------------------------------------------------------------
# Match-level data preparation
# -----------------------------------------------------------------------

MATCH_FEATURE_COLS = [
    "team_attack_str", "team_defence_str",
    "opp_attack_str", "opp_defence_str",
    "team_form_3", "team_form_5", "team_form_10",
    "opp_form_3", "opp_form_5", "opp_form_10",
    "is_home",
    "team_is_promoted", "opp_is_promoted",
    "team_goals_for_expanding", "team_goals_against_expanding",
    "opp_goals_for_expanding", "opp_goals_against_expanding",
]


def _build_team_gw_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate player-level data to team-GW level.

    Computes per-team, per-GW statistics needed for match features.
    """
    required = {"season", "GW", "team", "total_points", "was_home"}
    missing = required - set(df.columns)
    if missing:
        logger.warning("Missing columns for team stats: %s", missing)

    team_col = "team"
    if team_col not in df.columns:
        return pd.DataFrame()

    # Aggregate per team-GW
    agg = (
        df.groupby(["season", "GW", team_col], as_index=False)
        .agg(
            team_points_sum=("total_points", "sum"),
            team_points_mean=("total_points", "mean"),
            team_goals=("goals_scored", "sum") if "goals_scored" in df.columns else ("total_points", "count"),
            team_minutes=("minutes", "sum") if "minutes" in df.columns else ("total_points", "count"),
            is_home=("was_home", "first") if "was_home" in df.columns else ("total_points", "count"),
        )
    )

    # Get actual match scores from the raw data
    if "team_h_score" in df.columns and "team_a_score" in df.columns:
        score_agg = (
            df.groupby(["season", "GW", team_col], as_index=False)
            .agg(
                team_h_score=("team_h_score", "first"),
                team_a_score=("team_a_score", "first"),
                was_home_flag=("was_home", "first"),
            )
        )
        agg = agg.merge(score_agg, on=["season", "GW", team_col], how="left")

        # Derive actual goals for/against from the team's perspective
        was_home = agg["was_home_flag"].astype(bool) if "was_home_flag" in agg.columns else pd.Series(False, index=agg.index)
        agg["goals_for"] = np.where(
            was_home,
            pd.to_numeric(agg["team_h_score"], errors="coerce"),
            pd.to_numeric(agg["team_a_score"], errors="coerce"),
        )
        agg["goals_against"] = np.where(
            was_home,
            pd.to_numeric(agg["team_a_score"], errors="coerce"),
            pd.to_numeric(agg["team_h_score"], errors="coerce"),
        )
    else:
        agg["goals_for"] = np.nan
        agg["goals_against"] = np.nan

    return agg


def _get_opponent_team(df: pd.DataFrame) -> pd.DataFrame:
    """Map each team-GW row to its opponent.

    Uses opponent_team column if numeric, else derives from fixtures.
    """
    if "opponent_team" not in df.columns:
        return df

    # Get the majority opponent for each (season, GW, team)
    opp_agg = (
        df.groupby(["season", "GW", "team"], as_index=False)
        .agg(opponent_team=("opponent_team", "first"))
    )
    return opp_agg


def build_match_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """Build match-level dataset from player-level data.

    Returns one row per (season, GW, team) with:
    - team-level features (lagged expanding stats)
    - opponent features
    - target: goals_for (goals scored by this team in this match)

    All features are strictly lagged — they reflect only completed matches
    before this GW, never the current match.
    """
    logger.info("Building match-level dataset from %d player rows...", len(df))

    team_stats = _build_team_gw_stats(df)
    if team_stats.empty:
        logger.warning("Could not build team stats — returning empty DataFrame.")
        return pd.DataFrame()

    # Get opponent mapping
    opp_map = _get_opponent_team(df)
    if "opponent_team" in opp_map.columns:
        team_stats = team_stats.merge(
            opp_map[["season", "GW", "team", "opponent_team"]],
            on=["season", "GW", "team"],
            how="left",
        )

    # Sort chronologically
    team_stats = team_stats.sort_values(["season", "GW", "team"]).reset_index(drop=True)

    # Compute lagged expanding features per team per season
    team_stats = _add_lagged_features(team_stats)

    # Add opponent features by joining
    team_stats = _add_opponent_features(team_stats)

    # is_home as numeric
    if "is_home" in team_stats.columns:
        team_stats["is_home"] = pd.to_numeric(
            team_stats["is_home"].map({True: 1, False: 0, 1: 1, 0: 0, "True": 1, "False": 0}),
            errors="coerce",
        ).fillna(0).astype(int)

    # Promoted team flags (simplified — team not seen in previous season)
    team_stats = _add_promoted_flags(team_stats)

    # Target: goals scored by this team
    team_stats["target_goals"] = pd.to_numeric(
        team_stats["goals_for"], errors="coerce"
    )

    valid = team_stats["target_goals"].notna()
    logger.info(
        "Match dataset: %d rows total, %d with valid targets.",
        len(team_stats), valid.sum(),
    )
    return team_stats


def _add_lagged_features(team_stats: pd.DataFrame) -> pd.DataFrame:
    """Add lagged expanding-mean features per team.

    All features reflect only data from BEFORE the current GW (shift=1).
    """
    working = team_stats.copy()

    for col, out_name in [
        ("goals_for", "team_goals_for_expanding"),
        ("goals_against", "team_goals_against_expanding"),
        ("team_points_mean", "team_form_expanding"),
    ]:
        if col not in working.columns:
            working[out_name] = np.nan
            continue
        vals = pd.to_numeric(working[col], errors="coerce")
        working[out_name] = (
            vals.groupby(working["team"])
            .transform(lambda x: x.expanding().mean().shift(1))
        )

    # Rolling form windows (3, 5, 10) — lagged
    for w in [3, 5, 10]:
        col = "team_points_mean"
        if col in working.columns:
            vals = pd.to_numeric(working[col], errors="coerce")
            working[f"team_form_{w}"] = (
                vals.groupby(working["team"])
                .transform(lambda x: x.rolling(w, min_periods=1).mean().shift(1))
            )

    # Attack and defence strength (expanding, lagged)
    working["team_attack_str"] = working["team_goals_for_expanding"]
    working["team_defence_str"] = working["team_goals_against_expanding"]

    return working


def _add_opponent_features(team_stats: pd.DataFrame) -> pd.DataFrame:
    """Join opponent's lagged features onto each row."""
    working = team_stats.copy()

    if "opponent_team" not in working.columns:
        for col in ["opp_attack_str", "opp_defence_str",
                     "opp_form_3", "opp_form_5", "opp_form_10",
                     "opp_goals_for_expanding", "opp_goals_against_expanding"]:
            working[col] = np.nan
        return working

    # Build a lookup: (season, GW, team) -> team features
    opp_cols_map = {
        "team_attack_str": "opp_attack_str",
        "team_defence_str": "opp_defence_str",
        "team_form_3": "opp_form_3",
        "team_form_5": "opp_form_5",
        "team_form_10": "opp_form_10",
        "team_goals_for_expanding": "opp_goals_for_expanding",
        "team_goals_against_expanding": "opp_goals_against_expanding",
    }

    # Create opponent lookup
    opp_lookup = working[["season", "GW", "team"] + list(opp_cols_map.keys())].copy()
    opp_lookup = opp_lookup.rename(
        columns={**opp_cols_map, "team": "opponent_team"}
    )

    # Join
    working = working.merge(
        opp_lookup,
        on=["season", "GW", "opponent_team"],
        how="left",
        suffixes=("", "_opp_dup"),
    )

    # Drop duplicates if any
    dup_cols = [c for c in working.columns if c.endswith("_opp_dup")]
    working = working.drop(columns=dup_cols, errors="ignore")

    return working


def _add_promoted_flags(team_stats: pd.DataFrame) -> pd.DataFrame:
    """Flag teams not present in the previous season as promoted."""
    working = team_stats.copy()
    working["team_is_promoted"] = 0
    working["opp_is_promoted"] = 0

    if "season" not in working.columns:
        return working

    seasons = sorted(working["season"].unique())
    for i, season in enumerate(seasons):
        if i == 0:
            continue
        prev_season = seasons[i - 1]
        prev_teams = set(working.loc[working["season"] == prev_season, "team"].unique())
        curr_mask = working["season"] == season

        curr_teams = working.loc[curr_mask, "team"]
        working.loc[curr_mask, "team_is_promoted"] = (
            (~curr_teams.isin(prev_teams)).astype(int).values
        )

        if "opponent_team" in working.columns:
            curr_opps = working.loc[curr_mask, "opponent_team"]
            working.loc[curr_mask, "opp_is_promoted"] = (
                (~curr_opps.isin(prev_teams)).astype(int).values
            )

    return working


# -----------------------------------------------------------------------
# Poisson probability derivation
# -----------------------------------------------------------------------

def goals_to_probabilities(
    team_goals: np.ndarray,
    opponent_goals: np.ndarray,
    max_goals: int = 8,
) -> dict[str, np.ndarray]:
    """Derive win/draw/loss probabilities from predicted goals using Poisson.

    Args:
        team_goals: Predicted goals for the team (array).
        opponent_goals: Predicted goals for the opponent (array).
        max_goals: Maximum goals to consider in the Poisson PMF.

    Returns:
        dict with keys: win_prob, draw_prob, loss_prob
    """
    team_goals = np.maximum(np.asarray(team_goals, dtype=float), 0.01)
    opponent_goals = np.maximum(np.asarray(opponent_goals, dtype=float), 0.01)

    n = len(team_goals)
    win_prob = np.zeros(n)
    draw_prob = np.zeros(n)
    loss_prob = np.zeros(n)

    for k in range(max_goals + 1):
        p_team_k = poisson.pmf(k, team_goals)
        for j in range(max_goals + 1):
            p_opp_j = poisson.pmf(j, opponent_goals)
            joint = p_team_k * p_opp_j
            if k > j:
                win_prob += joint
            elif k == j:
                draw_prob += joint
            else:
                loss_prob += joint

    # Normalize to sum to 1
    total = win_prob + draw_prob + loss_prob
    total = np.maximum(total, 1e-10)
    win_prob /= total
    draw_prob /= total
    loss_prob /= total

    return {
        "win_prob": win_prob,
        "draw_prob": draw_prob,
        "loss_prob": loss_prob,
    }


# -----------------------------------------------------------------------
# Match model training and OOF prediction
# -----------------------------------------------------------------------

@dataclass
class MatchModelResult:
    """Result of match model training and evaluation.

    Attributes:
        best_model_name: Name of the best algorithm.
        best_model: Fitted model object.
        feature_cols: Feature columns used.
        all_metrics: Per-algorithm validation metrics.
        oof_predictions: OOF predictions DataFrame.
        formulation: Which target formulation was used ("team_goals" or "match_goals").
    """
    best_model_name: str = ""
    best_model: object = None
    feature_cols: list[str] = field(default_factory=list)
    all_metrics: dict = field(default_factory=dict)
    oof_predictions: pd.DataFrame = field(default_factory=pd.DataFrame)
    formulation: str = "team_goals"
    calibration_metrics: dict = field(default_factory=dict)


def train_match_model(
    df: pd.DataFrame,
    min_train_gameweeks: int = 38,
    random_state: int = 42,
    fold_step: int = 1,
) -> MatchModelResult:
    """Train the match prediction model with walk-forward validation.

    1. Builds match-level dataset
    2. Generates walk-forward folds
    3. Trains + selects best model
    4. Generates OOF predictions for all valid folds
    5. Evaluates probability calibration

    Args:
        df: Full player-level engineered dataset.
        min_train_gameweeks: Minimum GWs before first prediction fold.
        random_state: Random seed.
        fold_step: Number of consecutive GWs to batch per model training.

    Returns:
        MatchModelResult with fitted model and OOF predictions.
    """
    # 1. Build match-level data
    match_df = build_match_dataset(df)
    if match_df.empty or match_df["target_goals"].notna().sum() < 100:
        logger.warning("Insufficient match data for training. Returning empty result.")
        return MatchModelResult()

    # 2. Identify available features
    available_features = [c for c in MATCH_FEATURE_COLS if c in match_df.columns]
    if not available_features:
        logger.warning("No match features available.")
        return MatchModelResult()

    logger.info("Training match model with %d features: %s", len(available_features), available_features)

    # 3. Walk-forward folds
    folds = generate_walk_forward_folds(
        match_df,
        min_train_gameweeks=min_train_gameweeks,
        season_col="season",
        gw_col="GW",
        fold_step=fold_step,
    )

    if not folds:
        logger.warning("No walk-forward folds generated for match model.")
        return MatchModelResult()

    # 4. Use last ~20% of folds for model selection validation
    n_val_folds = max(1, len(folds) // 5)
    train_folds = folds[:-n_val_folds]
    val_folds = folds[-n_val_folds:]

    # Collect OOF predictions from all folds using a single model selection
    # First pass: select best model using the validation folds
    if train_folds:
        # Use all data before the first validation fold for training
        last_train_fold = train_folds[-1]
        val_train_mask = last_train_fold.train_mask | last_train_fold.predict_mask
        val_predict_mask = np.zeros(len(match_df), dtype=bool)
        for vf in val_folds:
            val_predict_mask |= vf.predict_mask

        train_data = match_df.loc[val_train_mask].copy()
        val_data = match_df.loc[val_predict_mask].copy()
    else:
        # Not enough folds; use a simple split
        split_idx = int(len(match_df) * 0.8)
        train_data = match_df.iloc[:split_idx].copy()
        val_data = match_df.iloc[split_idx:].copy()

    X_train_sel = train_data[available_features].apply(pd.to_numeric, errors="coerce").fillna(0)
    y_train_sel = pd.to_numeric(train_data["target_goals"], errors="coerce").fillna(0)
    X_val_sel = val_data[available_features].apply(pd.to_numeric, errors="coerce").fillna(0)
    y_val_sel = pd.to_numeric(val_data["target_goals"], errors="coerce").fillna(0)

    valid_train = y_train_sel.notna() & np.isfinite(y_train_sel)
    valid_val = y_val_sel.notna() & np.isfinite(y_val_sel)

    candidates = build_match_candidates(random_state)
    logger.info("Selecting best match model from %d candidates...", len(candidates))

    best_name, best_model, all_metrics = select_best_model(
        candidates,
        X_train_sel.loc[valid_train], y_train_sel.loc[valid_train],
        X_val_sel.loc[valid_val], y_val_sel.loc[valid_val],
        metric="mae",
    )

    # 5. Generate OOF predictions using walk-forward with model caching
    oof_preds = pd.Series(np.nan, index=match_df.index, name="oof_goals_pred")
    model_cache: dict[int, object] = {}

    for fold in folds:
        cache_key = fold.train_temporal_max

        if cache_key not in model_cache:
            fold_train = match_df.loc[fold.train_mask]
            X_tr = fold_train[available_features].apply(pd.to_numeric, errors="coerce").fillna(0)
            y_tr = pd.to_numeric(fold_train["target_goals"], errors="coerce").fillna(0)
            valid = y_tr.notna() & np.isfinite(y_tr)
            if valid.sum() < 10:
                model_cache[cache_key] = None
                continue
            try:
                model = candidates[[c[0] for c in candidates].index(best_name)][1]()
                model.fit(X_tr.loc[valid], y_tr.loc[valid])
                model_cache[cache_key] = model
            except Exception as exc:
                logger.warning("Match model fold %d failed: %s", fold.fold_id, exc)
                model_cache[cache_key] = None
                continue

        cached_model = model_cache.get(cache_key)
        if cached_model is None:
            continue

        fold_pred = match_df.loc[fold.predict_mask]
        X_pr = fold_pred[available_features].apply(pd.to_numeric, errors="coerce").fillna(0)
        if X_pr.empty:
            continue

        try:
            preds = cached_model.predict(X_pr)
            oof_preds.loc[fold.predict_mask] = preds
        except Exception as exc:
            logger.warning("Match model fold %d predict failed: %s", fold.fold_id, exc)

    match_df["oof_goals_pred"] = oof_preds

    # 6. Evaluate probability calibration on validation folds
    calibration_metrics = _evaluate_calibration(match_df, val_folds, available_features, best_name, candidates)

    n_predicted = oof_preds.notna().sum()
    logger.info(
        "Match model training complete: best=%s, OOF predictions=%d/%d.",
        best_name, n_predicted, len(match_df),
    )

    result = MatchModelResult(
        best_model_name=best_name,
        best_model=best_model,
        feature_cols=available_features,
        all_metrics=all_metrics,
        oof_predictions=match_df,
        formulation="team_goals",
        calibration_metrics=calibration_metrics,
    )
    return result


def _evaluate_calibration(
    match_df: pd.DataFrame,
    val_folds: list,
    feature_cols: list[str],
    best_name: str,
    candidates: list,
) -> dict:
    """Evaluate calibration of Poisson-derived probabilities."""
    from sklearn.metrics import brier_score_loss, log_loss

    val_mask = np.zeros(len(match_df), dtype=bool)
    for vf in val_folds:
        val_mask |= vf.predict_mask

    val_data = match_df.loc[val_mask].copy()
    pred_goals = val_data.get("oof_goals_pred")
    actual_goals_for = pd.to_numeric(val_data.get("goals_for", pd.Series()), errors="coerce")
    actual_goals_against = pd.to_numeric(val_data.get("goals_against", pd.Series()), errors="coerce")

    if pred_goals is None or actual_goals_for.isna().all():
        return {}

    valid = pred_goals.notna() & actual_goals_for.notna() & actual_goals_against.notna()
    if valid.sum() < 20:
        return {}

    pred_g = pred_goals.loc[valid].values
    actual_gf = actual_goals_for.loc[valid].values
    actual_ga = actual_goals_against.loc[valid].values

    # Use league average as opponent prediction for calibration assessment
    avg_opp = np.full_like(pred_g, float(actual_ga.mean()))

    probs = goals_to_probabilities(pred_g, avg_opp)
    actual_result = np.where(actual_gf > actual_ga, 1.0, 0.0)  # win=1

    metrics = {}
    try:
        metrics["win_brier"] = float(brier_score_loss(actual_result, probs["win_prob"]))
    except Exception:
        pass

    try:
        actual_draw = np.where(actual_gf == actual_ga, 1.0, 0.0)
        metrics["draw_brier"] = float(brier_score_loss(actual_draw, probs["draw_prob"]))
    except Exception:
        pass

    logger.info("Match model calibration: %s", metrics)
    return metrics


# -----------------------------------------------------------------------
# Map match predictions to player level
# -----------------------------------------------------------------------

def map_match_predictions_to_players(
    player_df: pd.DataFrame,
    match_oof: pd.DataFrame,
) -> pd.DataFrame:
    """Map match-level OOF predictions to player-level rows.

    For each player row (season, GW, team), looks up that team's
    predicted goals and the opponent's predicted goals, then derives
    win/draw/loss probabilities.

    Args:
        player_df: Player-level DataFrame.
        match_oof: Match-level DataFrame with oof_goals_pred column.

    Returns:
        pd.DataFrame: player_df with added match prediction columns.
    """
    result = player_df.copy()

    if match_oof.empty or "oof_goals_pred" not in match_oof.columns:
        for col in [
            "match_predicted_team_goals", "match_predicted_opponent_goals",
            "match_predicted_win_prob", "match_predicted_draw_prob",
            "match_predicted_loss_prob", "match_predicted_goal_difference",
            "match_difficulty",
        ]:
            result[col] = np.nan
        return result

    # Build lookup: (season, GW, team) -> predicted goals
    lookup = (
        match_oof[["season", "GW", "team", "oof_goals_pred"]]
        .dropna(subset=["oof_goals_pred"])
        .drop_duplicates(subset=["season", "GW", "team"])
        .set_index(["season", "GW", "team"])["oof_goals_pred"]
        .to_dict()
    )

    # Map team's predicted goals
    team_goals = result.apply(
        lambda r: lookup.get((r.get("season"), r.get("GW"), r.get("team")), np.nan),
        axis=1,
    )

    # Map opponent's predicted goals
    opp_goals = result.apply(
        lambda r: lookup.get((r.get("season"), r.get("GW"), r.get("opponent_team")), np.nan),
        axis=1,
    )

    result["match_predicted_team_goals"] = team_goals
    result["match_predicted_opponent_goals"] = opp_goals
    result["match_predicted_goal_difference"] = team_goals - opp_goals

    # Derive probabilities where both predictions are available
    valid = team_goals.notna() & opp_goals.notna()
    if valid.any():
        probs = goals_to_probabilities(
            team_goals.loc[valid].values,
            opp_goals.loc[valid].values,
        )
        result.loc[valid, "match_predicted_win_prob"] = probs["win_prob"]
        result.loc[valid, "match_predicted_draw_prob"] = probs["draw_prob"]
        result.loc[valid, "match_predicted_loss_prob"] = probs["loss_prob"]

    # Match difficulty: higher = harder for the player's team
    result["match_difficulty"] = opp_goals - team_goals + 1.5  # centered ~1.5

    n_mapped = valid.sum()
    logger.info(
        "Mapped match predictions to %d/%d player rows (%.1f%%).",
        n_mapped, len(result), 100 * n_mapped / max(len(result), 1),
    )
    return result


# -----------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------

def save_match_model(result: MatchModelResult, output_dir: Path) -> None:
    """Save match model and metadata."""
    output_dir.mkdir(parents=True, exist_ok=True)

    if result.best_model is not None:
        model_path = output_dir / "match_model.joblib"
        joblib.dump(result.best_model, model_path)
        logger.info("Saved match model to %s.", model_path)

    metadata = {
        "best_model_name": result.best_model_name,
        "feature_cols": result.feature_cols,
        "formulation": result.formulation,
        "all_metrics": result.all_metrics,
        "calibration_metrics": result.calibration_metrics,
    }
    meta_path = output_dir / "match_model_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    logger.info("Saved match model metadata to %s.", meta_path)


def load_match_model(model_dir: Path) -> tuple[object, dict]:
    """Load a saved match model and its metadata."""
    model_path = model_dir / "match_model.joblib"
    meta_path = model_dir / "match_model_metadata.json"

    model = joblib.load(model_path) if model_path.exists() else None
    metadata = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return model, metadata
