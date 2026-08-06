"""Validation check for missing values."""

from __future__ import annotations

import pandas as pd

from src.validation.checks.base import ValidationCheck
from src.validation.models import CheckResult, ValidationIssue


class MissingValuesCheck(ValidationCheck):
    """Flags missing values, treating required columns as hard failures.

    Required columns (e.g. ``season``, a player identifier, the target
    variable) must have zero missing values for the check to pass.
    Missing values in any other column are still reported for
    visibility, but do not fail the check on their own.

    Args:
        required_columns: Columns that must never contain missing
            values.
        max_issues_in_report: Maximum number of individual issues to
            retain in the returned :class:`CheckResult` (the true
            total is still reported via ``total_issue_count``).
    """

    def __init__(
        self,
        required_columns: tuple[str, ...],
        max_issues_in_report: int = 50,
    ) -> None:
        self._required_columns = required_columns
        self._max_issues_in_report = max_issues_in_report

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this check."""
        return "missing_values"

    def run(self, data: pd.DataFrame) -> CheckResult:
        """Check for missing values, failing only on required columns.

        Args:
            data: The dataset to validate.

        Returns:
            CheckResult: Outcome of the missing-values check.
        """
        issues: list[ValidationIssue] = []
        missing_counts = data.isna().sum()
        columns_with_missing = missing_counts[missing_counts > 0]

        required_present = [c for c in self._required_columns if c in data.columns]
        required_missing_columns: list[str] = []

        for column, count in columns_with_missing.items():
            pct = round(100 * count / len(data), 2) if len(data) else 0.0
            is_required = column in required_present
            if is_required:
                required_missing_columns.append(str(column))
            issues.append(
                ValidationIssue(
                    column=str(column),
                    row_index=None,
                    description=(
                        f"{'[REQUIRED] ' if is_required else ''}"
                        f"{count} missing value(s) ({pct}%)"
                    ),
                )
            )

        passed = not required_missing_columns
        summary = (
            "No missing values in required columns."
            if passed
            else f"Missing values found in required column(s): {required_missing_columns}."
        )
        if columns_with_missing.any() and passed:
            summary += f" ({len(columns_with_missing)} non-required column(s) also have missing values.)"

        return CheckResult(
            check_name=self.name,
            passed=passed,
            issues=issues[: self._max_issues_in_report],
            total_issue_count=len(issues),
            summary=summary,
        )
