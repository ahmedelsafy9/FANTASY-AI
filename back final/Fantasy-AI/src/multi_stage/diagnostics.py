"""Diagnostic reports and ablation analysis for the multi-stage pipeline.

Generates comparison tables, high-score analysis, calibration reports,
position-specific breakdowns, and model selection summaries.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger

logger = get_logger(__name__)


def generate_ablation_report(
    ablation_results: dict,
    output_path: Path,
) -> str:
    """Generate the mandatory ablation comparison report.

    Args:
        ablation_results: Dict mapping config name to metrics dict.
        output_path: Path to write the markdown report.

    Returns:
        str: The report as markdown text.
    """
    lines = [
        "# Multi-Stage Pipeline — Ablation Study Report",
        "",
        "## Configuration Comparison",
        "",
    ]

    if not ablation_results:
        lines.append("*No ablation results available.*")
        report = "\n".join(lines)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report, encoding="utf-8")
        return report

    # Main comparison table
    metric_keys = ["mae", "rmse", "r2", "spearman",
                   "recall_6", "recall_8", "recall_10", "recall_12",
                   "precision_6", "top_20_recall"]

    header = "| Configuration | Model |"
    separator = "|---|---|"
    for mk in metric_keys:
        display = mk.upper().replace("_", " ")
        header += f" {display} |"
        separator += "---|"

    lines.append(header)
    lines.append(separator)

    config_display = {
        "A_baseline": "Baseline (FB3)",
        "B_plus_match": "+ Match Preds",
        "C_plus_contrib": "+ Contrib Preds",
        "D_full": "+ Match + Contrib",
    }

    for config_name in ["A_baseline", "B_plus_match", "C_plus_contrib", "D_full"]:
        if config_name not in ablation_results:
            continue
        m = ablation_results[config_name]
        display_name = config_display.get(config_name, config_name)
        model_name = m.get("model", "?")
        row = f"| {display_name} | {model_name} |"
        for mk in metric_keys:
            val = m.get(mk, float("nan"))
            if isinstance(val, float) and not np.isnan(val):
                row += f" {val:.4f} |"
            else:
                row += " — |"
        lines.append(row)

    # Improvement analysis
    lines.extend(["", "## Improvement Over Baseline", ""])

    baseline = ablation_results.get("A_baseline", {})
    baseline_mae = baseline.get("mae")

    if baseline_mae is not None:
        for config_name in ["B_plus_match", "C_plus_contrib", "D_full"]:
            if config_name not in ablation_results:
                continue
            m = ablation_results[config_name]
            config_mae = m.get("mae")
            if config_mae is not None:
                delta = baseline_mae - config_mae
                pct = 100 * delta / baseline_mae if baseline_mae > 0 else 0
                direction = "improvement" if delta > 0 else "degradation"
                lines.append(
                    f"- **{config_display.get(config_name, config_name)}**: "
                    f"MAE Δ = {delta:+.4f} ({pct:+.2f}% {direction})"
                )

    # High-score analysis
    lines.extend(["", "## High-Score Performance", ""])
    lines.append("| Configuration | Recall≥6 | Recall≥8 | Recall≥10 | Recall≥12 | Precision≥6 |")
    lines.append("|---|---|---|---|---|---|")

    for config_name in ["A_baseline", "B_plus_match", "C_plus_contrib", "D_full"]:
        if config_name not in ablation_results:
            continue
        m = ablation_results[config_name]
        display_name = config_display.get(config_name, config_name)
        row = f"| {display_name} |"
        for k in ["recall_6", "recall_8", "recall_10", "recall_12", "precision_6"]:
            val = m.get(k, float("nan"))
            if isinstance(val, float) and not np.isnan(val):
                row += f" {val:.4f} |"
            else:
                row += " — |"
        lines.append(row)

    # Model selection per task
    lines.extend(["", "## Best Model Per Task", ""])

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    logger.info("Ablation report written to %s.", output_path)
    return report


def generate_model_selection_report(
    match_result,
    contribution_result,
    ablation_results: dict,
    output_path: Path,
) -> str:
    """Generate the model selection report showing best model per task."""
    lines = [
        "# Model Selection Report",
        "",
        "| Task | Best Model | Primary Metric | Value |",
        "|---|---|---|---|",
    ]

    # Match model
    match_name = None
    match_val = "—"
    cal_metrics = {}
    if match_result:
        if isinstance(match_result, dict):
            match_name = match_result.get("best_model_name")
            metrics = match_result.get("all_metrics", {}).get(match_name, {})
            match_val = metrics.get("mae", "—")
            cal_metrics = match_result.get("calibration_metrics", {})
        else:
            match_name = getattr(match_result, "best_model_name", None)
            if match_name:
                metrics = getattr(match_result, "all_metrics", {}).get(match_name, {})
                match_val = metrics.get("mae", "—")
                cal_metrics = getattr(match_result, "calibration_metrics", {})

    if match_name:
        val_str = f"{match_val:.4f}" if isinstance(match_val, (int, float)) else str(match_val)
        lines.append(f"| Match Prediction | {match_name} | MAE | {val_str} |")

    # Contribution models
    if contribution_result:
        if isinstance(contribution_result, dict):
            for target_name, target_info in contribution_result.items():
                if isinstance(target_info, dict) and "best_model_name" in target_info:
                    b_name = target_info["best_model_name"]
                    v_mae = target_info.get("val_mae", float("nan"))
                    val_str = f"{v_mae:.4f}" if np.isfinite(v_mae) else "—"
                    lines.append(f"| {target_name} | {b_name} | MAE | {val_str} |")
        else:
            for target_name, tr in getattr(contribution_result, "target_results", {}).items():
                if tr.best_model_name:
                    lines.append(
                        f"| {target_name} | {tr.best_model_name} | MAE | {tr.val_mae:.4f} |"
                    )

    # Points model (from ablation)
    best_config = None
    best_mae = float("inf")
    for config_name, m in ablation_results.items():
        mae = m.get("mae", float("inf"))
        if mae < best_mae:
            best_mae = mae
            best_config = config_name

    if best_config:
        model_name = ablation_results[best_config].get("model", "?")
        lines.append(f"| FPL Points | {model_name} ({best_config}) | MAE | {best_mae:.4f} |")

    # Production recommendation
    lines.extend(["", "## Production Recommendation", ""])
    baseline_mae = ablation_results.get("A_baseline", {}).get("mae")
    if baseline_mae is not None and best_config and best_config != "A_baseline":
        delta = baseline_mae - best_mae
        if delta > 0:
            lines.append(
                f"**Recommend promoting {best_config}** — MAE improved by {delta:.4f} "
                f"({100*delta/baseline_mae:.2f}%) over baseline."
            )
        else:
            lines.append(
                "**Recommend keeping Feedback 3 baseline** — multi-stage pipeline "
                "did not improve MAE on out-of-time validation."
            )
    elif best_config == "A_baseline":
        lines.append(
            "**Recommend keeping Feedback 3 baseline** — it performed best."
        )

    # Calibration section
    lines.extend(["", "## Probability Calibration", ""])
    if cal_metrics:
        for metric_name, val in cal_metrics.items():
            lines.append(f"- **{metric_name}**: {val:.4f}")
    else:
        lines.append("*No calibration data available.*")

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    logger.info("Model selection report written to %s.", output_path)
    return report


def generate_diagnostic_report(
    augmented_data: pd.DataFrame,
    ablation_results: dict,
    match_result,
    contribution_result,
    output_path: Path,
) -> str:
    """Generate comprehensive diagnostic report."""
    lines = [
        "# Multi-Stage Pipeline — Diagnostic Report",
        "",
    ]

    # Dataset summary
    lines.extend(["## Dataset Summary", ""])
    if not augmented_data.empty:
        lines.append(f"- Total rows: {len(augmented_data):,}")
        if "season" in augmented_data.columns:
            seasons = sorted(augmented_data["season"].unique())
            lines.append(f"- Seasons: {len(seasons)} ({seasons[0]} to {seasons[-1]})")
        if "match_predicted_team_goals" in augmented_data.columns:
            cov = augmented_data["match_predicted_team_goals"].notna().sum()
            lines.append(f"- Match prediction coverage: {cov:,} / {len(augmented_data):,} ({100*cov/len(augmented_data):.1f}%)")
        for col in ["contrib_predicted_goals", "contrib_predicted_assists", "contrib_clean_sheet_probability"]:
            if col in augmented_data.columns:
                cov = augmented_data[col].notna().sum()
                lines.append(f"- {col} coverage: {cov:,} ({100*cov/len(augmented_data):.1f}%)")

    # Position-specific analysis
    lines.extend(["", "## Position-Specific Performance", ""])
    if "position" in augmented_data.columns and "total_points" in augmented_data.columns:
        for pos in ["GK", "GKP", "DEF", "MID", "FWD"]:
            pos_data = augmented_data[augmented_data["position"] == pos]
            if len(pos_data) > 0:
                avg_pts = pos_data["total_points"].mean()
                lines.append(f"- **{pos}**: {len(pos_data):,} rows, avg points = {avg_pts:.2f}")

    # Match model diagnostics
    if match_result and match_result.best_model_name:
        lines.extend(["", "## Match Model Diagnostics", ""])
        lines.append(f"- Best algorithm: {match_result.best_model_name}")
        lines.append(f"- Formulation: {match_result.formulation}")
        lines.append(f"- Features: {len(match_result.feature_cols)}")
        if match_result.all_metrics:
            for model_name, metrics in match_result.all_metrics.items():
                lines.append(f"  - {model_name}: {metrics}")

    # Contribution model diagnostics
    if contribution_result and contribution_result.target_results:
        lines.extend(["", "## Contribution Model Diagnostics", ""])
        for target_name, tr in contribution_result.target_results.items():
            lines.append(f"- **{target_name}**: best={tr.best_model_name}, MAE={tr.val_mae:.4f}")
            if tr.all_metrics:
                for model_name, metrics in tr.all_metrics.items():
                    lines.append(f"  - {model_name}: {metrics}")

    report = "\n".join(lines)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    logger.info("Diagnostic report written to %s.", output_path)
    return report
