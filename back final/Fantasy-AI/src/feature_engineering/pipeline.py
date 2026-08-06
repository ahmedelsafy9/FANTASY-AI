"""Orchestrator that runs a sequence of feature engineering steps over a dataset.

Mirrors the Dependency Inversion pattern used throughout the project:
:class:`FeaturePipeline` depends only on the abstract
:class:`~src.feature_engineering.steps.base.FeatureStep` interface,
never on a concrete step.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeaturePipelineResult, FeatureStepSummary
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)


class FeaturePipeline:
    """Runs a sequence of :class:`FeatureStep` instances over a dataset.

    Args:
        steps: The steps to run, in order. Injected by the caller —
            the pipeline has no knowledge of which concrete steps
            exist. Step order matters: e.g. ``FormIndexStep`` depends
            on columns produced by an earlier ``RollingAverageStep``.
    """

    def __init__(self, steps: Sequence[FeatureStep]) -> None:
        self._steps = list(steps)

    def run(self, data: pd.DataFrame) -> FeaturePipelineResult:
        """Run every configured step, in order, over ``data``.

        Args:
            data: The cleaned dataset to derive features from.

        Returns:
            FeaturePipelineResult: The engineered dataset plus a
            per-step audit trail of what was added.
        """
        rows_before = len(data)
        current = data
        summaries: list[FeatureStepSummary] = []

        for step in self._steps:
            logger.info("Running feature engineering step '%s'...", step.name)
            current, summary = step.apply(current)
            summaries.append(summary)

        result = FeaturePipelineResult(
            data=current,
            generated_at=datetime.now(timezone.utc),
            rows_before=rows_before,
            rows_after=len(current),
            step_summaries=summaries,
        )
        total_columns_added = sum(len(s.columns_added) for s in summaries)
        logger.info(
            "Feature engineering complete: %d row(s), %d feature column(s) added across "
            "%d step(s).",
            result.rows_after,
            total_columns_added,
            len(summaries),
        )
        return result
