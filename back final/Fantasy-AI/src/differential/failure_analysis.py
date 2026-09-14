"""Failure and success analysis for differential predictions.

Analyzes why certain differential players hit or missed:
    1. Missed Breakouts (False Negatives): Low-ownership players scoring >= 8 points that the model failed to highlight.
       Root causes:
       - 'Sudden Playing Time': Low prior minutes, unexpectedly started or played full 90.
       - 'Clinical Finishing Variance': Outperformed very low expected metrics (e.g., scored from 0.05 xG).
       - 'Fixture Defiance': Produced big points despite playing top-4 opposition (FDR >= 4).
       - 'Model Bias': Had strong opportunity/underlying metrics but was penalized by ownership or price.
    2. Successful Differential Anticipations (True Positives): Low-ownership players the model ranked highly who delivered.
"""

from __future__ import annotations

from dataclasses import dataclass
import pandas as pd
import numpy as np

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class FailureAnalysisResult:
    """Report on differential hits, misses, and failure taxonomy."""
    total_breakouts: int
    anticipated_breakouts: int
    missed_breakouts: int
    recall_rate: float
    failure_cause_breakdown: dict[str, int]
    top_missed_examples: list[dict]
    top_anticipated_examples: list[dict]
    summary_markdown: str


def run_failure_analysis(
    df: pd.DataFrame,
    score_col: str,
    target_col: str = "total_points",
    ownership_col: str = "ownership_percentile",
    threshold: int = 8,
    top_k_threshold: int = 25,
) -> FailureAnalysisResult:
    """Analyze historical true differential breakouts vs model predictions.

    Args:
        df: Scored evaluation DataFrame with features, metadata, and actual outcomes.
        score_col: Column name containing the model/differential score.
        target_col: Outcome column (default 'total_points').
        ownership_col: Ownership percentile column.
        threshold: Score threshold defining a breakout (default 8).
        top_k_threshold: Per-GW rank threshold considered 'anticipated'.

    Returns:
        FailureAnalysisResult with taxonomy and concrete player examples.
    """
    logger.info("Running Failure & Success Analysis on differential picks...")

    work_df = df.copy()
    work_df["_actual_pts"] = pd.to_numeric(work_df[target_col], errors="coerce").fillna(0)
    work_df["_score"] = pd.to_numeric(work_df[score_col], errors="coerce").fillna(0)
    work_df["_own"] = pd.to_numeric(work_df.get(ownership_col, 0.5), errors="coerce").fillna(0.5)

    # Differential players: ownership <= 25th percentile
    is_diff = work_df["_own"] <= 0.25
    is_breakout = (work_df["_actual_pts"] >= threshold) & is_diff

    breakout_df = work_df[is_breakout].copy()
    total_breakouts = len(breakout_df)

    if total_breakouts == 0:
        return FailureAnalysisResult(
            total_breakouts=0, anticipated_breakouts=0, missed_breakouts=0,
            recall_rate=0.0, failure_cause_breakdown={}, top_missed_examples=[],
            top_anticipated_examples=[], summary_markdown="No breakouts found in evaluation dataset.",
        )

    # Compute per-GW rank of score
    work_df["_gw_rank"] = work_df.groupby(["season", "GW"])["_score"].rank(ascending=False, method="min")
    breakout_df["_gw_rank"] = work_df.loc[breakout_df.index, "_gw_rank"]

    # Anticipated: ranked in top_k in that GW
    breakout_df["is_hit"] = breakout_df["_gw_rank"] <= top_k_threshold

    hits = breakout_df[breakout_df["is_hit"]].copy()
    misses = breakout_df[~breakout_df["is_hit"]].copy()

    anticipated_count = len(hits)
    missed_count = len(misses)
    recall = anticipated_count / total_breakouts

    # Classify failure causes for missed breakouts
    causes = {
        "Sudden Playing Time Surge": 0,
        "Extreme Finishing Variance": 0,
        "Fixture Defiance (FDR >= 4)": 0,
        "Model Underestimation": 0,
    }

    missed_examples = []
    for _, row in misses.iterrows():
        prev_min = float(row.get("minutes_avg_last_5", 0.0) or 0.0)
        curr_min = float(row.get("minutes", 0.0) or 0.0)
        curr_xg = float(row.get("expected_goals", 0.0) or 0.0)
        curr_xa = float(row.get("expected_assists", 0.0) or 0.0)
        fdr = float(row.get("fixture_difficulty", 3.0) or 3.0)

        assigned_cause = "Model Underestimation"
        if prev_min < 45.0 and curr_min >= 60.0:
            assigned_cause = "Sudden Playing Time Surge"
        elif (curr_xg + curr_xa) < 0.20 and float(row["_actual_pts"]) >= 10:
            assigned_cause = "Extreme Finishing Variance"
        elif fdr >= 4.0:
            assigned_cause = "Fixture Defiance (FDR >= 4)"

        causes[assigned_cause] += 1

        name = str(row.get("name", row.get("element", "Player")))
        team = str(row.get("team", ""))
        missed_examples.append({
            "player": name,
            "team": team,
            "season": str(row.get("season", "")),
            "gw": int(row.get("GW", 0)),
            "points": int(row["_actual_pts"]),
            "rank": int(row["_gw_rank"]),
            "cause": assigned_cause,
        })

    # Sort missed by highest points
    missed_examples = sorted(missed_examples, key=lambda x: x["points"], reverse=True)[:10]

    # Top hits
    top_hits = []
    for _, row in hits.sort_values(by="_actual_pts", ascending=False).head(10).iterrows():
        name = str(row.get("name", row.get("element", "Player")))
        team = str(row.get("team", ""))
        top_hits.append({
            "player": name,
            "team": team,
            "season": str(row.get("season", "")),
            "gw": int(row.get("GW", 0)),
            "points": int(row["_actual_pts"]),
            "rank": int(row["_gw_rank"]),
            "score": round(float(row["_score"]), 3),
        })

    summary_md = (
        f"### Differential Prediction Failure & Success Audit\n\n"
        f"- **Total Differential Breakout Events (pts >= {threshold}, own <= 25%):** {total_breakouts}\n"
        f"- **Anticipated in Top-{top_k_threshold} per GW:** {anticipated_count} ({recall * 100:.1f}%)\n"
        f"- **Missed Breakouts:** {missed_count} ({(1 - recall) * 100:.1f}%)\n\n"
        f"#### Taxonomy of Missed Breakouts:\n"
        f"- **Sudden Playing Time Surge:** {causes['Sudden Playing Time Surge']} "
        f"({causes['Sudden Playing Time Surge'] / max(missed_count, 1) * 100:.1f}%)\n"
        f"- **Extreme Finishing Variance (Low xGI):** {causes['Extreme Finishing Variance']} "
        f"({causes['Extreme Finishing Variance'] / max(missed_count, 1) * 100:.1f}%)\n"
        f"- **Fixture Defiance (FDR >= 4):** {causes['Fixture Defiance (FDR >= 4)']} "
        f"({causes['Fixture Defiance (FDR >= 4)'] / max(missed_count, 1) * 100:.1f}%)\n"
        f"- **Model Underestimation / Rank Deficiency:** {causes['Model Underestimation']} "
        f"({causes['Model Underestimation'] / max(missed_count, 1) * 100:.1f}%)\n"
    )

    return FailureAnalysisResult(
        total_breakouts=total_breakouts,
        anticipated_breakouts=anticipated_count,
        missed_breakouts=missed_count,
        recall_rate=round(recall, 4),
        failure_cause_breakdown=causes,
        top_missed_examples=missed_examples,
        top_anticipated_examples=top_hits,
        summary_markdown=summary_md,
    )
