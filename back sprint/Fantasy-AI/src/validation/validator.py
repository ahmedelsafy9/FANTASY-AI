"""Orchestrator that runs a collection of validation checks over a dataset.

Mirrors the same Dependency Inversion pattern used elsewhere in the
project: :class:`DatasetValidator` depends only on the abstract
:class:`~src.validation.checks.base.ValidationCheck` interface, never
on a concrete check, so checks can be added, removed, or reordered
freely by whatever constructs the validator.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import pandas as pd

from src.config.logging_config import get_logger
from src.validation.checks.base import ValidationCheck
from src.validation.models import ValidationReport

logger = get_logger(__name__)


class DatasetValidator:
    """Runs a sequence of :class:`ValidationCheck` instances over a dataset.

    Args:
        checks: The checks to run, in order. Injected by the caller —
            the validator has no knowledge of which concrete checks
            exist.
    """

    def __init__(self, checks: Sequence[ValidationCheck]) -> None:
        self._checks = list(checks)

    def validate(self, data: pd.DataFrame) -> ValidationReport:
        """Run every configured check against ``data``.

        Args:
            data: The dataset to validate.

        Returns:
            ValidationReport: Aggregated results of every check.
        """
        report = ValidationReport(
            generated_at=datetime.now(timezone.utc),
            row_count=len(data),
            column_count=data.shape[1],
        )

        for check in self._checks:
            logger.info("Running validation check '%s'...", check.name)
            result = check.run(data)
            report.results.append(result)
            status = "PASSED" if result.passed else "FAILED"
            logger.info("Check '%s' %s: %s", check.name, status, result.summary)

        logger.info(
            "Validation complete: %d/%d checks passed, %d total issue(s).",
            sum(1 for r in report.results if r.passed),
            len(report.results),
            report.total_issue_count,
        )
        return report
