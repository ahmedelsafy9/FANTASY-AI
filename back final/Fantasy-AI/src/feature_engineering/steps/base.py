"""Abstract interface every feature engineering step must implement.

Mirrors the Dependency Inversion pattern used throughout the project:
:class:`~src.feature_engineering.pipeline.FeaturePipeline` depends
only on this interface, never on a concrete step.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.feature_engineering.models import FeatureStepSummary


class FeatureStep(ABC):
    """Abstract base class for a single, focused feature engineering step."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        raise NotImplementedError

    @abstractmethod
    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """Apply this step's feature derivation to the data.

        Args:
            data: The DataFrame to derive features from. Implementations
                must not mutate this object in place — return a new/
                copied DataFrame instead.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with new
            feature column(s) added, and a summary describing what was
            added.
        """
        raise NotImplementedError
