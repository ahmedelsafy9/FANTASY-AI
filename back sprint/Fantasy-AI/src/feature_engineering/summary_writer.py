"""Writer that renders a :class:`~src.feature_engineering.models.FeaturePipelineResult`
as a small, machine-readable JSON summary.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger
from src.feature_engineering.models import FeaturePipelineResult

logger = get_logger(__name__)


def write_summary(result: FeaturePipelineResult, summary_path: Path) -> None:
    """Write a JSON summary of a feature engineering run to disk.

    Args:
        result: The pipeline result to summarize.
        summary_path: Destination file path.
    """
    ensure_directory(summary_path.parent)

    payload = {
        "generated_at": result.generated_at.isoformat(),
        "rows_before": result.rows_before,
        "rows_after": result.rows_after,
        "columns_after": result.data.shape[1],
        "steps": [asdict(summary) for summary in result.step_summaries],
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote feature engineering summary to %s.", summary_path)
