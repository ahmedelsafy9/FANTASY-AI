"""Orchestrator that runs a sequence of preprocessing steps over a dataset.

Mirrors the Dependency Inversion pattern used throughout the project:
:class:`PreprocessingPipeline` depends only on the abstract
:class:`~src.preprocessing.steps.base.PreprocessingStep` interface,
never on a concrete step.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from src.config.logging_config import get_logger
from src.preprocessing.steps.base import PreprocessingStep, StepSummary

logger = get_logger(__name__)


@dataclass
class PipelineResult:
    """The outcome of running a full :class:`PreprocessingPipeline`.

    Attributes:
        data: The cleaned DataFrame.
        generated_at: When the pipeline finished running.
        rows_before: Row count before any step ran.
        rows_after: Row count after every step ran.
        step_summaries: One :class:`StepSummary` per step, in order.
    """

    data: pd.DataFrame = field(repr=False)
    generated_at: datetime
    rows_before: int
    rows_after: int
    step_summaries: list[StepSummary] = field(default_factory=list)


class PreprocessingPipeline:
    """Runs a sequence of :class:`PreprocessingStep` instances over a dataset.

    Args:
        steps: The steps to run, in order. Injected by the caller —
            the pipeline has no knowledge of which concrete steps
            exist.
    """

    def __init__(self, steps: Sequence[PreprocessingStep]) -> None:
        self._steps = list(steps)

    def run(self, data: pd.DataFrame) -> PipelineResult:
        """Run every configured step, in order, over ``data``.

        Args:
            data: The raw dataset to clean.

        Returns:
            PipelineResult: The cleaned dataset plus a per-step audit
            trail of what changed.
        """
        rows_before = len(data)
        current = data
        summaries: list[StepSummary] = []

        for step in self._steps:
            logger.info("Running preprocessing step '%s'...", step.name)
            current, summary = step.apply(current)
            summaries.append(summary)

        result = PipelineResult(
            data=current,
            generated_at=datetime.now(timezone.utc),
            rows_before=rows_before,
            rows_after=len(current),
            step_summaries=summaries,
        )
        logger.info(
            "Preprocessing complete: %d -> %d rows across %d step(s).",
            result.rows_before,
            result.rows_after,
            len(summaries),
        )
        return result
