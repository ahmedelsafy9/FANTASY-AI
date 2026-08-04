"""Validation check for invalid Gameweek numbers."""

from __future__ import annotations

import pandas as pd

from src.validation.checks.base import ValidationCheck
from src.validation.models import CheckResult, ValidationIssue


class GameweekCheck(ValidationCheck):
    """Flags Gameweek values outside the valid range or non-integer.

    Args:
        gameweek_columns: Candidate column names that identify the
            Gameweek (e.g. ``("GW", "round")``). The first one present
            in the data is used.
        min_gameweek: Minimum valid Gameweek number (inclusive).
        max_gameweek: Maximum valid Gameweek number (inclusive).
        max_issues_in_report: Maximum number of individual issues to
            retain in the returned :class:`CheckResult`.
    """

    def __init__(
        self,
        gameweek_columns: tuple[str, ...],
        min_gameweek: int,
        max_gameweek: int,
        max_issues_in_report: int = 50,
    ) -> None:
        self._gameweek_columns = gameweek_columns
        self._min_gameweek = min_gameweek
        self._max_gameweek = max_gameweek
        self._max_issues_in_report = max_issues_in_report

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this check."""
        return "gameweek_range"

    def run(self, data: pd.DataFrame) -> CheckResult:
        """Check that Gameweek values fall within the configured valid range.

        Args:
            data: The dataset to validate.

        Returns:
            CheckResult: Outcome of the Gameweek check. Passes
            trivially (with a note in the summary) if no Gameweek
            column is present in the data.
        """
        gw_column = next((c for c in self._gameweek_columns if c in data.columns), None)
        if gw_column is None:
            return CheckResult(
                check_name=self.name,
                passed=True,
                issues=[],
                total_issue_count=0,
                summary=(
                    f"No Gameweek column found among {self._gameweek_columns}; "
                    "check skipped."
                ),
            )

        numeric_gw = pd.to_numeric(data[gw_column], errors="coerce")
        invalid_mask = (
            numeric_gw.isna()
            | (numeric_gw < self._min_gameweek)
            | (numeric_gw > self._max_gameweek)
        )

        issues: list[ValidationIssue] = []
        for idx, raw_value in data.loc[invalid_mask, gw_column].items():
            if len(issues) >= self._max_issues_in_report:
                break
            issues.append(
                ValidationIssue(
                    column=gw_column,
                    row_index=int(idx),
                    description=(
                        f"Invalid Gameweek value {raw_value!r}; expected "
                        f"{self._min_gameweek}-{self._max_gameweek}."
                    ),
                )
            )

        total_issue_count = int(invalid_mask.sum())
        passed = total_issue_count == 0
        summary = (
            f"All '{gw_column}' values within {self._min_gameweek}-{self._max_gameweek}."
            if passed
            else f"{total_issue_count} invalid '{gw_column}' value(s) found."
        )

        return CheckResult(
            check_name=self.name,
            passed=passed,
            issues=issues[: self._max_issues_in_report],
            total_issue_count=total_issue_count,
            summary=summary,
        )
