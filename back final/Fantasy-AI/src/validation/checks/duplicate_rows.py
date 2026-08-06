"""Validation check for duplicate rows."""

from __future__ import annotations

import pandas as pd

from src.validation.checks.base import ValidationCheck
from src.validation.models import CheckResult, ValidationIssue


class DuplicateRowsCheck(ValidationCheck):
    """Flags fully duplicate rows and duplicate logical keys.

    Two kinds of duplication are checked:

    1. Fully identical rows (every column matches another row).
    2. Duplicate "logical keys" — e.g. the same player appearing twice
       for the same season and Gameweek, which should never happen
       even if some other column differs.

    Args:
        key_columns: Columns that, together, should uniquely identify
            a row (e.g. ``("season", "name", "GW")``). Only the subset
            of these columns actually present in the data is used.
        max_issues_in_report: Maximum number of individual issues to
            retain in the returned :class:`CheckResult`.
    """

    def __init__(
        self,
        key_columns: tuple[str, ...],
        max_issues_in_report: int = 50,
    ) -> None:
        self._key_columns = key_columns
        self._max_issues_in_report = max_issues_in_report

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this check."""
        return "duplicate_rows"

    def run(self, data: pd.DataFrame) -> CheckResult:
        """Check for fully duplicate rows and duplicate logical keys.

        Args:
            data: The dataset to validate.

        Returns:
            CheckResult: Outcome of the duplicate-rows check.
        """
        issues: list[ValidationIssue] = []

        full_duplicate_mask = data.duplicated(keep="first")
        for idx in data.index[full_duplicate_mask][: self._max_issues_in_report]:
            issues.append(
                ValidationIssue(
                    column=None,
                    row_index=int(idx),
                    description="Fully duplicate row.",
                )
            )
        full_duplicate_count = int(full_duplicate_mask.sum())

        available_key_columns = [c for c in self._key_columns if c in data.columns]
        key_duplicate_count = 0
        if available_key_columns:
            key_duplicate_mask = data.duplicated(subset=available_key_columns, keep="first")
            key_duplicate_count = int(key_duplicate_mask.sum())
            remaining_slots = max(0, self._max_issues_in_report - len(issues))
            for idx in data.index[key_duplicate_mask][:remaining_slots]:
                issues.append(
                    ValidationIssue(
                        column=", ".join(available_key_columns),
                        row_index=int(idx),
                        description=f"Duplicate key {available_key_columns}.",
                    )
                )

        total_issue_count = full_duplicate_count + key_duplicate_count
        passed = total_issue_count == 0

        summary_parts = [f"{full_duplicate_count} fully duplicate row(s)"]
        if available_key_columns:
            summary_parts.append(
                f"{key_duplicate_count} duplicate key row(s) on {available_key_columns}"
            )
        summary = ", ".join(summary_parts) + "."

        return CheckResult(
            check_name=self.name,
            passed=passed,
            issues=issues[: self._max_issues_in_report],
            total_issue_count=total_issue_count,
            summary=summary,
        )
