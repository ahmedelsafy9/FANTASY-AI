"""Abstract interface every preprocessing step must implement.

Mirrors the same Dependency Inversion pattern used for ``DataSource``
and ``ValidationCheck``: :class:`~src.preprocessing.pipeline.PreprocessingPipeline`
depends only on this interface, never on a concrete step.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import pandas as pd


@dataclass
class StepSummary:
    """A record of what a single preprocessing step did.

    Attributes:
        step_name: Identifier of the step that produced this summary.
        rows_before: Row count before the step ran.
        rows_after: Row count after the step ran.
        description: Human-readable note on what changed.
    """

    step_name: str
    rows_before: int
    rows_after: int
    description: str


class PreprocessingStep(ABC):
    """Abstract base class for a single, focused data-cleaning step."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        raise NotImplementedError

    @abstractmethod
    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        """Apply this step's transformation to the data.

        Args:
            data: The DataFrame to transform. Implementations must not
                mutate this object in place — return a new/copied
                DataFrame instead, so failed pipelines never leave the
                caller's data partially modified.

        Returns:
            tuple[pd.DataFrame, StepSummary]: The transformed data and
            a summary describing what changed.
        """
        raise NotImplementedError
