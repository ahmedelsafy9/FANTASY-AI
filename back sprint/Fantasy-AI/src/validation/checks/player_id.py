"""Validation check for invalid player identifiers."""

from __future__ import annotations

import pandas as pd

from src.validation.checks.base import ValidationCheck
from src.validation.models import CheckResult, ValidationIssue


class PlayerIdCheck(ValidationCheck):
    """Flags missing, blank, or non-positive player identifiers.

    The first column found (in order) from ``player_id_columns`` is
    used as the identifier. Numeric identifier columns (e.g. FPL's
    ``element`` ID) must be positive integers; string identifier
    columns (e.g. ``name``) must be non-empty, non-whitespace values.

    Args:
        player_id_columns: Candidate column names that identify a
            player, in priority order.
        max_issues_in_report: Maximum number of individual issues to
            retain in the returned :class:`CheckResult`.
    """

    def __init__(
        self,
        player_id_columns: tuple[str, ...],
        max_issues_in_report: int = 50,
    ) -> None:
        self._player_id_columns = player_id_columns
        self._max_issues_in_report = max_issues_in_report

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this check."""
        return "player_identifiers"

    def run(self, data: pd.DataFrame) -> CheckResult:
        """Check that player identifiers are present and well-formed.

        Args:
            data: The dataset to validate.

        Returns:
            CheckResult: Outcome of the player-identifier check.
        """
        id_column = next(
            (c for c in self._player_id_columns if c in data.columns), None
        )
        if id_column is None:
            return CheckResult(
                check_name=self.name,
                passed=True,
                issues=[],
                total_issue_count=0,
                summary=(
                    f"No player identifier column found among "
                    f"{self._player_id_columns}; check skipped."
                ),
            )

        if pd.api.types.is_numeric_dtype(data[id_column]):
            invalid_mask = data[id_column].isna() | (data[id_column] <= 0)
            reason = "non-positive or missing numeric identifier"
        else:
            stripped = data[id_column].astype(str).str.strip()
            invalid_mask = data[id_column].isna() | (stripped == "") | (stripped == "nan")
            reason = "missing or blank identifier"

        issues: list[ValidationIssue] = []
        for idx, raw_value in data.loc[invalid_mask, id_column].items():
            if len(issues) >= self._max_issues_in_report:
                break
            issues.append(
                ValidationIssue(
                    column=id_column,
                    row_index=int(idx),
                    description=f"Invalid player identifier ({reason}): {raw_value!r}.",
                )
            )

        total_issue_count = int(invalid_mask.sum())
        passed = total_issue_count == 0
        summary = (
            f"All '{id_column}' values are valid player identifiers."
            if passed
            else f"{total_issue_count} invalid '{id_column}' value(s) found ({reason})."
        )

        return CheckResult(
            check_name=self.name,
            passed=passed,
            issues=issues[: self._max_issues_in_report],
            total_issue_count=total_issue_count,
            summary=summary,
        )
