"""Validation check for invalid data types."""

from __future__ import annotations

import pandas as pd

from src.validation.checks.base import ValidationCheck
from src.validation.models import CheckResult, ValidationIssue


class DataTypeCheck(ValidationCheck):
    """Flags values in expected-numeric columns that fail to parse as numbers.

    Rather than trusting pandas' inferred dtype (which can be
    ``object`` even for a mostly-numeric column with a few bad rows),
    this check attempts to coerce every value in each expected-numeric
    column and reports exactly which values fail.

    Args:
        expected_numeric_columns: Columns that should contain only
            numeric values.
        max_issues_in_report: Maximum number of individual issues to
            retain in the returned :class:`CheckResult`.
    """

    def __init__(
        self,
        expected_numeric_columns: tuple[str, ...],
        max_issues_in_report: int = 50,
    ) -> None:
        self._expected_numeric_columns = expected_numeric_columns
        self._max_issues_in_report = max_issues_in_report

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this check."""
        return "data_types"

    def run(self, data: pd.DataFrame) -> CheckResult:
        """Check that expected-numeric columns contain only parseable numbers.

        Args:
            data: The dataset to validate.

        Returns:
            CheckResult: Outcome of the data-type check.
        """
        issues: list[ValidationIssue] = []
        affected_columns: set[str] = set()

        for column in self._expected_numeric_columns:
            if column not in data.columns:
                continue
            coerced = pd.to_numeric(data[column], errors="coerce")
            invalid_mask = coerced.isna() & data[column].notna()
            invalid_count = int(invalid_mask.sum())
            if invalid_count == 0:
                continue
            affected_columns.add(column)
            for idx, raw_value in data.loc[invalid_mask, column].items():
                if len(issues) >= self._max_issues_in_report:
                    break
                issues.append(
                    ValidationIssue(
                        column=column,
                        row_index=int(idx),
                        description=f"Non-numeric value {raw_value!r} in numeric column.",
                    )
                )

        total_issue_count = sum(
            int(
                (
                    pd.to_numeric(data[c], errors="coerce").isna() & data[c].notna()
                ).sum()
            )
            for c in self._expected_numeric_columns
            if c in data.columns
        )
        passed = total_issue_count == 0
        summary = (
            "All expected-numeric columns parse cleanly."
            if passed
            else f"Non-numeric values found in column(s): {sorted(affected_columns)}."
        )

        return CheckResult(
            check_name=self.name,
            passed=passed,
            issues=issues[: self._max_issues_in_report],
            total_issue_count=total_issue_count,
            summary=summary,
        )
