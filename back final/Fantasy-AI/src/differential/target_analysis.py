"""Target distribution analysis for breakout player prediction.

Computes historical distributions of FPL total_points to determine
data-driven thresholds for defining "high-score" and "breakout" events.

All analysis uses strictly historical data with no temporal leakage.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DistributionStats:
    """Summary statistics for a total_points distribution slice."""
    group_label: str
    n_rows: int
    mean: float
    median: float
    std: float
    p75: float
    p90: float
    p95: float
    p99: float
    maximum: float
    freq_6_plus: float
    freq_8_plus: float
    freq_10_plus: float
    freq_12_plus: float


@dataclass
class TargetAnalysisResult:
    """Complete target distribution analysis."""
    overall: DistributionStats | None = None
    by_season: list[DistributionStats] = field(default_factory=list)
    by_position: list[DistributionStats] = field(default_factory=list)
    by_price_band: list[DistributionStats] = field(default_factory=list)
    by_ownership_band: list[DistributionStats] = field(default_factory=list)
    breakout_threshold: float = 0.0
    recommended_target: str = ""


def _compute_stats(
    points: pd.Series,
    label: str,
) -> DistributionStats:
    """Compute distribution statistics for a series of total_points values."""
    pts = pd.to_numeric(points, errors="coerce").dropna()
    n = len(pts)
    if n == 0:
        return DistributionStats(
            group_label=label, n_rows=0,
            mean=0, median=0, std=0,
            p75=0, p90=0, p95=0, p99=0, maximum=0,
            freq_6_plus=0, freq_8_plus=0, freq_10_plus=0, freq_12_plus=0,
        )
    return DistributionStats(
        group_label=label,
        n_rows=n,
        mean=float(pts.mean()),
        median=float(pts.median()),
        std=float(pts.std()),
        p75=float(np.percentile(pts, 75)),
        p90=float(np.percentile(pts, 90)),
        p95=float(np.percentile(pts, 95)),
        p99=float(np.percentile(pts, 99)),
        maximum=float(pts.max()),
        freq_6_plus=float((pts >= 6).mean()),
        freq_8_plus=float((pts >= 8).mean()),
        freq_10_plus=float((pts >= 10).mean()),
        freq_12_plus=float((pts >= 12).mean()),
    )


def _assign_price_band(value: pd.Series) -> pd.Series:
    """Assign price bands from the FPL value column (in tenths, e.g. 55 = £5.5M)."""
    v = pd.to_numeric(value, errors="coerce").fillna(0)
    bins = [0, 45, 55, 70, 90, 120, float("inf")]
    labels = ["Budget (<=4.5)", "Low (4.6-5.5)", "Mid (5.6-7.0)",
              "Premium (7.1-9.0)", "Elite (9.1-12.0)", "Ultra (>12.0)"]
    return pd.cut(v, bins=bins, labels=labels, right=True)


def _assign_ownership_band(
    selected: pd.Series,
    season: pd.Series,
    gw: pd.Series,
) -> pd.Series:
    """Assign ownership bands using rank-based percentiles within each (season, GW)."""
    df_temp = pd.DataFrame({
        "selected": pd.to_numeric(selected, errors="coerce").fillna(0),
        "season": season,
        "gw": pd.to_numeric(gw, errors="coerce").fillna(0),
    })
    # Compute percentile rank within each (season, GW)
    df_temp["ownership_pctl"] = df_temp.groupby(["season", "gw"])["selected"].rank(pct=True)

    bins = [0, 0.05, 0.20, 0.50, 0.80, 1.0]
    labels = ["Ultra-Low (<5%)", "Low (5-20%)", "Medium (20-50%)",
              "Popular (50-80%)", "Template (>80%)"]
    return pd.cut(df_temp["ownership_pctl"], bins=bins, labels=labels, right=True, include_lowest=True)


def analyze_target_distribution(
    df: pd.DataFrame,
    target_col: str = "total_points",
    value_col: str = "value",
    selected_col: str = "selected",
    season_col: str = "season",
    gw_col: str = "GW",
) -> TargetAnalysisResult:
    """Perform comprehensive target distribution analysis.

    Computes statistics by season, position, price band, and ownership band.

    Args:
        df: Full historical dataset with features.
        target_col: Target column name.
        value_col: Player price column.
        selected_col: Ownership count column.
        season_col: Season column.
        gw_col: Gameweek column.

    Returns:
        TargetAnalysisResult with all distribution statistics.
    """
    result = TargetAnalysisResult()
    points = pd.to_numeric(df[target_col], errors="coerce").dropna()

    # Overall
    result.overall = _compute_stats(points, "Overall")
    logger.info(
        "Overall target: N=%d, Mean=%.3f, Std=%.3f, >=6: %.2f%%, >=8: %.2f%%, >=10: %.2f%%, >=12: %.2f%%",
        result.overall.n_rows, result.overall.mean, result.overall.std,
        result.overall.freq_6_plus * 100, result.overall.freq_8_plus * 100,
        result.overall.freq_10_plus * 100, result.overall.freq_12_plus * 100,
    )

    # By season
    if season_col in df.columns:
        for season in sorted(df[season_col].dropna().unique()):
            mask = df[season_col] == season
            stats = _compute_stats(df.loc[mask, target_col], f"Season: {season}")
            result.by_season.append(stats)
            logger.info(
                "  %s: N=%d, >=8: %.2f%%, >=10: %.2f%%",
                stats.group_label, stats.n_rows, stats.freq_8_plus * 100, stats.freq_10_plus * 100,
            )

    # By position
    pos_cols = ["is_position_gkp", "is_position_def", "is_position_mid", "is_position_fwd"]
    pos_names = ["GKP", "DEF", "MID", "FWD"]
    for col, name in zip(pos_cols, pos_names):
        if col in df.columns:
            mask = pd.to_numeric(df[col], errors="coerce").fillna(0) == 1
            stats = _compute_stats(df.loc[mask, target_col], f"Position: {name}")
            result.by_position.append(stats)
            logger.info(
                "  %s: N=%d, >=8: %.2f%%, >=10: %.2f%%",
                stats.group_label, stats.n_rows, stats.freq_8_plus * 100, stats.freq_10_plus * 100,
            )

    # By price band
    if value_col in df.columns:
        price_bands = _assign_price_band(df[value_col])
        for band in price_bands.cat.categories:
            mask = price_bands == band
            if mask.sum() > 0:
                stats = _compute_stats(df.loc[mask, target_col], f"Price: {band}")
                result.by_price_band.append(stats)
                logger.info(
                    "  %s: N=%d, >=8: %.2f%%, >=10: %.2f%%",
                    stats.group_label, stats.n_rows, stats.freq_8_plus * 100, stats.freq_10_plus * 100,
                )

    # By ownership band
    if selected_col in df.columns and season_col in df.columns and gw_col in df.columns:
        ownership_bands = _assign_ownership_band(df[selected_col], df[season_col], df[gw_col])
        for band in ownership_bands.cat.categories:
            mask = ownership_bands == band
            if mask.sum() > 0:
                stats = _compute_stats(df.loc[mask, target_col], f"Ownership: {band}")
                result.by_ownership_band.append(stats)
                logger.info(
                    "  %s: N=%d, >=8: %.2f%%, >=10: %.2f%%",
                    stats.group_label, stats.n_rows, stats.freq_8_plus * 100, stats.freq_10_plus * 100,
                )

    # Determine breakout threshold
    # A breakout = scoring significantly above the player's recent baseline
    # Use the P90 of (actual - baseline) among players with baseline > 0
    if "total_points_avg_last_5" in df.columns:
        baseline = pd.to_numeric(df["total_points_avg_last_5"], errors="coerce")
        actual = pd.to_numeric(df[target_col], errors="coerce")
        valid = baseline.notna() & actual.notna() & (baseline > 0)
        if valid.sum() > 100:
            surplus = actual[valid] - baseline[valid]
            # P90 of the positive surplus = threshold for "breakout"
            positive_surplus = surplus[surplus > 0]
            if len(positive_surplus) > 100:
                result.breakout_threshold = float(np.percentile(positive_surplus, 75))
                logger.info(
                    "Breakout threshold (P75 of positive surplus): %.2f points above baseline.",
                    result.breakout_threshold,
                )

    # Recommend target based on class balance
    # Want a target with ~3-10% positive rate for reasonable classification
    if result.overall:
        if 0.03 <= result.overall.freq_8_plus <= 0.10:
            result.recommended_target = "total_points >= 8"
        elif 0.03 <= result.overall.freq_10_plus <= 0.10:
            result.recommended_target = "total_points >= 10"
        elif result.overall.freq_6_plus <= 0.15:
            result.recommended_target = "total_points >= 6"
        else:
            result.recommended_target = "total_points >= 8"
        logger.info("Recommended primary target: %s", result.recommended_target)

    return result


def format_analysis_report(result: TargetAnalysisResult) -> str:
    """Format the target analysis as a markdown report."""
    lines = ["# Target Distribution Analysis\n"]

    if result.overall:
        lines.append("## Overall Distribution\n")
        o = result.overall
        lines.append(f"| Metric | Value |")
        lines.append(f"|---|---|")
        lines.append(f"| N | {o.n_rows:,} |")
        lines.append(f"| Mean | {o.mean:.3f} |")
        lines.append(f"| Median | {o.median:.1f} |")
        lines.append(f"| Std | {o.std:.3f} |")
        lines.append(f"| P75 | {o.p75:.1f} |")
        lines.append(f"| P90 | {o.p90:.1f} |")
        lines.append(f"| P95 | {o.p95:.1f} |")
        lines.append(f"| P99 | {o.p99:.1f} |")
        lines.append(f"| Max | {o.maximum:.0f} |")
        lines.append(f"| Freq ≥6 | {o.freq_6_plus * 100:.2f}% |")
        lines.append(f"| Freq ≥8 | {o.freq_8_plus * 100:.2f}% |")
        lines.append(f"| Freq ≥10 | {o.freq_10_plus * 100:.2f}% |")
        lines.append(f"| Freq ≥12 | {o.freq_12_plus * 100:.2f}% |")
        lines.append("")

    def _table(items: list[DistributionStats], title: str) -> list[str]:
        if not items:
            return []
        t = [f"## {title}\n"]
        t.append("| Group | N | Mean | ≥6% | ≥8% | ≥10% | ≥12% | P90 | P95 |")
        t.append("|---|---|---|---|---|---|---|---|---|")
        for s in items:
            t.append(
                f"| {s.group_label} | {s.n_rows:,} | {s.mean:.2f} | "
                f"{s.freq_6_plus * 100:.1f}% | {s.freq_8_plus * 100:.1f}% | "
                f"{s.freq_10_plus * 100:.1f}% | {s.freq_12_plus * 100:.1f}% | "
                f"{s.p90:.1f} | {s.p95:.1f} |"
            )
        t.append("")
        return t

    lines.extend(_table(result.by_season, "By Season"))
    lines.extend(_table(result.by_position, "By Position"))
    lines.extend(_table(result.by_price_band, "By Price Band"))
    lines.extend(_table(result.by_ownership_band, "By Ownership Band"))

    if result.breakout_threshold > 0:
        lines.append(f"## Breakout Threshold\n")
        lines.append(f"Data-driven breakout threshold: **{result.breakout_threshold:.2f}** points above player's recent baseline (`total_points_avg_last_5`).\n")

    lines.append(f"## Recommended Target\n")
    lines.append(f"**{result.recommended_target}** (based on class balance analysis)\n")

    return "\n".join(lines)
