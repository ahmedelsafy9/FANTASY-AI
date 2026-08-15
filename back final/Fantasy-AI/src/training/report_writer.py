"""Writer that renders a :class:`~src.training.models.TrainingResult`
as a human-readable Markdown comparison report.
"""

from __future__ import annotations

from pathlib import Path

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger
from src.training.models import TrainingResult

logger = get_logger(__name__)


def write_comparison_report(result: TrainingResult, report_path: Path) -> None:
    """Render a model comparison report as Markdown and write it to disk.

    Args:
        result: The training result to render.
        report_path: Destination file path.
    """
    ensure_directory(report_path.parent)

    sorted_results = sorted(result.results, key=lambda r: r.metrics.mae)

    # Build a lookup from model name to composite scores (if available)
    composite_lookup: dict = {}
    if result.composite_scores:
        for score in result.composite_scores:
            composite_lookup[score.model_name] = score

    has_composite = bool(composite_lookup)

    lines: list[str] = [
        "# Fantasy-AI — Machine Learning Baseline Comparison Report",
        "",
        f"Generated: {result.generated_at.isoformat()}",
        f"Target: `{result.target_column}`",
        f"Train rows: **{result.train_rows}** | Test rows: **{result.test_rows}**",
        f"Feature count: **{len(result.feature_columns)}**",
        "",
        f"## Best Model: `{result.best_model_name}` 🏆",
        "",
        "## Model Comparison",
        "",
    ]

    if has_composite:
        lines.append(
            "| Model | MAE ↓ | RMSE ↓ | R² ↑ | Spearman ρ ↑ | ≥6 Recall ↑ | ≥10 Recall ↑ "
            "| ≥6 Precision ↑ | Composite ↑ | Train Time (s) |"
        )
        lines.append(
            "|-------|-------|--------|------|-------------|-------------|-------------|"
            "---------------|-------------|----------------|"
        )
    else:
        lines.append("| Model | MAE ↓ | RMSE ↓ | R² ↑ | Train Time (s) |")
        lines.append("|-------|-------|--------|------|----------------|")

    for model_result in sorted_results:
        marker = " 🏆" if model_result.name == result.best_model_name else ""
        if has_composite and model_result.name in composite_lookup:
            cs = composite_lookup[model_result.name]
            fm = cs.fpl_metrics
            eligible_marker = "" if cs.eligible else " ⛔"
            lines.append(
                f"| {model_result.name}{marker}{eligible_marker} "
                f"| {model_result.metrics.mae:.4f} "
                f"| {model_result.metrics.rmse:.4f} "
                f"| {model_result.metrics.r2:.4f} "
                f"| {fm.spearman_rho:.4f} "
                f"| {fm.recall_6:.4f} "
                f"| {fm.recall_10:.4f} "
                f"| {fm.precision_6:.4f} "
                f"| {cs.composite_score:.4f} "
                f"| {model_result.train_seconds:.2f} |"
            )
        else:
            lines.append(
                f"| {model_result.name}{marker} | {model_result.metrics.mae:.4f} | "
                f"{model_result.metrics.rmse:.4f} | {model_result.metrics.r2:.4f} | "
                f"{model_result.train_seconds:.2f} |"
            )

    if has_composite:
        # Add gate failure details
        gate_failures = [
            (score.model_name, score.gate_failures)
            for score in result.composite_scores
            if score.gate_failures
        ]
        if gate_failures:
            lines += ["", "### Eligibility Gate Failures", ""]
            for name, failures in gate_failures:
                lines.append(f"- **{name}**: {', '.join(failures)}")

    if result.skipped_models:
        lines += ["", "## Skipped Models", "", "| Model | Reason |", "|-------|--------|"]
        for name, reason in result.skipped_models.items():
            lines.append(f"| {name} | {reason} |")

    lines += [
        "",
        "## Feature Columns Used",
        "",
        f"```\n{', '.join(result.feature_columns)}\n```",
        "",
    ]

    report_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Wrote model comparison report to %s.", report_path)
