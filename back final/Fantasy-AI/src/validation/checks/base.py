"""Abstract interface every validation check must implement.

Following the same Dependency Inversion pattern used for
:class:`~src.data_collection.interfaces.data_source.DataSource`, the
:class:`DatasetValidator` orchestrator depends only on this interface,
never on a concrete check. New checks can be added, removed, or
reordered without touching the orchestrator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.validation.models import CheckResult


class ValidationCheck(ABC):
    """Abstract base class for a single, focused dataset validation check."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A short, human-readable identifier for this check."""
        raise NotImplementedError

    @abstractmethod
    def run(self, data: pd.DataFrame) -> CheckResult:
        """Run this check against a dataset.

        Args:
            data: The dataset to validate. Implementations must treat
                this as read-only.

        Returns:
            CheckResult: The outcome of the check.
        """
        raise NotImplementedError
