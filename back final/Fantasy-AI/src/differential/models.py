"""Data models for the differential prediction system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DifferentialMetrics:
    """Evaluation metrics for a differential model or baseline."""
    name: str = ""
    threshold: int = 8
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    precision_at_20: float = 0.0
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    pr_auc: float = 0.0
    roc_auc: float = 0.0
    top_k_hit_rate: float = 0.0
    spearman: float = 0.0
    ndcg_at_10: float = 0.0
    ndcg_at_20: float = 0.0
    differential_hit_rate_8: float = 0.0
    differential_hit_rate_10: float = 0.0
    differential_hit_rate_12: float = 0.0
    n_evaluated: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "threshold": self.threshold,
            "precision_at_5": round(self.precision_at_5, 4),
            "precision_at_10": round(self.precision_at_10, 4),
            "precision_at_20": round(self.precision_at_20, 4),
            "recall_at_10": round(self.recall_at_10, 4),
            "recall_at_20": round(self.recall_at_20, 4),
            "pr_auc": round(self.pr_auc, 4),
            "roc_auc": round(self.roc_auc, 4),
            "top_k_hit_rate": round(self.top_k_hit_rate, 4),
            "spearman": round(self.spearman, 4),
            "ndcg_at_10": round(self.ndcg_at_10, 4),
            "ndcg_at_20": round(self.ndcg_at_20, 4),
            "differential_hit_rate_8": round(self.differential_hit_rate_8, 4),
            "differential_hit_rate_10": round(self.differential_hit_rate_10, 4),
            "differential_hit_rate_12": round(self.differential_hit_rate_12, 4),
            "n_evaluated": self.n_evaluated,
        }


@dataclass
class DifferentialModelResult:
    """Result of a trained differential model."""
    model_name: str = ""
    model_type: str = ""  # "single_threshold", "multi_threshold", "breakout"
    model: object = None
    feature_cols: list[str] = field(default_factory=list)
    train_medians: dict[str, float] = field(default_factory=dict)
    threshold: int = 8
    metrics: DifferentialMetrics | None = None
    all_candidate_metrics: dict[str, dict] = field(default_factory=dict)


@dataclass
class DifferentialPrediction:
    """A single differential prediction for a player."""
    element: int | None = None
    name: str = ""
    team: str = ""
    position: str = ""
    price: float = 0.0
    ownership_pct: float = 0.0
    ownership_percentile: float = 0.0
    predicted_expected_points: float = 0.0
    p_6_plus: float = 0.0
    p_8_plus: float = 0.0
    p_10_plus: float = 0.0
    p_12_plus: float = 0.0
    differential_score: float = 0.0
    differential_category: str = ""
    predicted_gameweek: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "element": self.element,
            "name": self.name,
            "team": self.team,
            "position": self.position,
            "price": round(self.price, 1),
            "ownership_pct": round(self.ownership_pct, 2),
            "ownership_percentile": round(self.ownership_percentile, 3),
            "predicted_expected_points": round(self.predicted_expected_points, 2),
            "p_6_plus": round(self.p_6_plus, 3),
            "p_8_plus": round(self.p_8_plus, 3),
            "p_10_plus": round(self.p_10_plus, 3),
            "p_12_plus": round(self.p_12_plus, 3),
            "differential_score": round(self.differential_score, 3),
            "differential_category": self.differential_category,
            "predicted_gameweek": self.predicted_gameweek,
        }


@dataclass
class ScoringFormulaResult:
    """Result of testing a differential scoring formula."""
    name: str
    formula_description: str
    hit_rate_8: float = 0.0
    hit_rate_10: float = 0.0
    hit_rate_12: float = 0.0
    avg_points_top10: float = 0.0
    avg_points_top20: float = 0.0
    spearman_vs_actual: float = 0.0
