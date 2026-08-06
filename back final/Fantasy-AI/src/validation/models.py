"""Domain models shared by every validation check and the report writer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ValidationIssue:
    """A single, specific problem found in a dataset.

    Attributes:
        column: Column the issue relates to, or ``None`` if the issue
            is row-level or dataset-level.
        row_index: Index of the affected row, or ``None`` if the issue
            spans multiple rows (e.g. an aggregate statistic).
        description: Human-readable description of the problem.
    """

    column: str | None
    row_index: int | None
    description: str


@dataclass
class CheckResult:
    """The outcome of running a single :class:`ValidationCheck`.

    Attributes:
        check_name: Identifier of the check that produced this result.
        passed: Whether the dataset passed this check.
        issues: Specific issues found (may be a truncated sample for
            very large issue counts — see ``total_issue_count``).
        total_issue_count: The true total number of issues found, even
            when ``issues`` has been truncated for report readability.
        summary: One-line human-readable summary of the outcome.
    """

    check_name: str
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    total_issue_count: int = 0
    summary: str = ""


@dataclass
class ValidationReport:
    """Aggregate result of running every check against a dataset.

    Attributes:
        generated_at: When the report was produced.
        row_count: Number of rows in the validated dataset.
        column_count: Number of columns in the validated dataset.
        results: One :class:`CheckResult` per check that was run.
    """

    generated_at: datetime
    row_count: int
    column_count: int
    results: list[CheckResult] = field(default_factory=list)

    @property
    def overall_passed(self) -> bool:
        """Whether every individual check passed.

        Returns:
            bool: ``True`` only if all checks in ``results`` passed.
        """
        return all(result.passed for result in self.results)

    @property
    def total_issue_count(self) -> int:
        """Sum of ``total_issue_count`` across all checks.

        Returns:
            int: Total number of issues found across every check.
        """
        return sum(result.total_issue_count for result in self.results)
