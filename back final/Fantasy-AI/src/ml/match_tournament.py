"""Independent match-prediction tournament.

Product semantics (preserved from ``src.multi_stage.match_model``):
predict expected home and away goals, then derive home-win / draw /
away-win probabilities with independent Poisson scorelines.

This is **not** a player-points regression task. Metrics are therefore
goal MAE/RMSE plus probability log loss and multiclass Brier score.
Accuracy is secondary only.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import poisson
from sklearn.metrics import mean_absolute_error, mean_squared_error, log_loss

from src.ml.tournament import (
    TournamentSplit,
    build_regression_candidates,
    _fit_predict,
    _blend,
    ENSEMBLE_MAE_IMPROVEMENT,
)


def poisson_outcome_probabilities(home_goals: np.ndarray, away_goals: np.ndarray, max_goals: int = 8) -> np.ndarray:
    """Return (n, 3) probabilities for home win, draw, away win."""
    home_goals = np.clip(np.asarray(home_goals, dtype=float), 0.05, 8.0)
    away_goals = np.clip(np.asarray(away_goals, dtype=float), 0.05, 8.0)
    rows = []
    for mu_h, mu_a in zip(home_goals, away_goals):
        home_pmf = poisson.pmf(np.arange(max_goals + 1), mu_h)
        away_pmf = poisson.pmf(np.arange(max_goals + 1), mu_a)
        joint = np.outer(home_pmf, away_pmf)
        home_win = float(np.tril(joint, -1).sum())
        draw = float(np.trace(joint))
        away_win = float(np.triu(joint, 1).sum())
        total = home_win + draw + away_win
        rows.append([home_win / total, draw / total, away_win / total])
    return np.asarray(rows)


def multiclass_brier(y_one_hot: np.ndarray, probs: np.ndarray) -> float:
    """Mean squared error between one-hot outcomes and predicted probabilities."""
    return float(np.mean(np.sum((y_one_hot - probs) ** 2, axis=1)))


def outcome_one_hot(home_goals: np.ndarray, away_goals: np.ndarray) -> np.ndarray:
    """Encode actual scorelines as home/draw/away one-hot rows."""
    encoded = np.zeros((len(home_goals), 3), dtype=float)
    for i, (home, away) in enumerate(zip(home_goals, away_goals)):
        if home > away:
            encoded[i, 0] = 1.0
        elif home == away:
            encoded[i, 1] = 1.0
        else:
            encoded[i, 2] = 1.0
    return encoded


@dataclass
class MatchTournamentReport:
    """Match-model comparison outcome."""

    selected: str
    ensemble_selected: bool
    rationale: str
    results: dict[str, dict[str, float]]
    target: str
    selection_rule: str


def run_match_goal_tournament(
    home_split: TournamentSplit,
    away_split: TournamentSplit,
    random_state: int = 42,
) -> MatchTournamentReport:
    """Compare GBM models on home/away goal regression, then Poisson probabilities."""
    candidates = build_regression_candidates(random_state)
    val_scores: dict[str, dict[str, float]] = {}
    test_scores: dict[str, dict[str, float]] = {}
    val_home: dict[str, np.ndarray] = {}
    val_away: dict[str, np.ndarray] = {}

    for name, builder in candidates:
        h_val = _fit_predict(builder, home_split.X_train, home_split.y_train, home_split.X_val, False)
        a_val = _fit_predict(builder, away_split.X_train, away_split.y_train, away_split.X_val, False)
        val_home[name] = h_val
        val_away[name] = a_val
        val_scores[name] = _score_match(home_split.y_val, away_split.y_val, h_val, a_val)

        h_test = _fit_predict(builder, home_split.X_train, home_split.y_train, home_split.X_test, False)
        a_test = _fit_predict(builder, away_split.X_train, away_split.y_train, away_split.X_test, False)
        test_scores[name] = _score_match(home_split.y_test, away_split.y_test, h_test, a_test)

    names = list(val_home)
    mean_h = _blend([val_home[name] for name in names])
    mean_a = _blend([val_away[name] for name in names])
    val_scores["mean_ensemble"] = _score_match(home_split.y_val, away_split.y_val, mean_h, mean_a)

    best_name = min((name for name in names), key=lambda n: val_scores[n]["goal_mae"])
    best = val_scores[best_name]
    ensemble = val_scores["mean_ensemble"]
    use_ensemble = ensemble["goal_mae"] <= best["goal_mae"] * (1.0 - ENSEMBLE_MAE_IMPROVEMENT)
    selected = "mean_ensemble" if use_ensemble else best_name
    rationale = (
        "Mean ensemble selected on validation goal MAE."
        if use_ensemble
        else f"Individual match model {best_name} retained; ensemble did not improve goal MAE enough."
    )
    return MatchTournamentReport(
        selected=selected,
        ensemble_selected=use_ensemble,
        rationale=rationale,
        results=test_scores,
        target="home_and_away_goals_then_poisson_1x2",
        selection_rule=(
            "Minimize validation goal MAE (home+away). Accept mean ensemble only "
            "with >=1% MAE improvement. Probability log loss and Brier are reported, "
            "not used to steal a player-regression winner."
        ),
    )


def _score_match(y_home, y_away, p_home, p_away) -> dict[str, float]:
    goal_mae = float(
        (mean_absolute_error(y_home, p_home) + mean_absolute_error(y_away, p_away)) / 2.0
    )
    goal_rmse = float(
        (
            np.sqrt(mean_squared_error(y_home, p_home))
            + np.sqrt(mean_squared_error(y_away, p_away))
        )
        / 2.0
    )
    probs = poisson_outcome_probabilities(p_home, p_away)
    one_hot = outcome_one_hot(y_home, y_away)
    labels = one_hot.argmax(axis=1)
    return {
        "goal_mae": goal_mae,
        "goal_rmse": goal_rmse,
        "log_loss": float(log_loss(labels, probs, labels=[0, 1, 2])),
        "brier": multiclass_brier(one_hot, probs),
        "accuracy": float((probs.argmax(axis=1) == labels).mean()),
    }
