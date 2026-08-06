"""Unit tests for DatasetValidator, the default-checks factory, and the report writer."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config.settings import ValidationSettings
from src.validation.checks.base import ValidationCheck
from src.validation.factory import build_default_checks
from src.validation.models import CheckResult
from src.validation.report_writer import write_markdown_report
from src.validation.validator import DatasetValidator


class _AlwaysPassCheck(ValidationCheck):
    @property
    def name(self) -> str:
        return "always_pass"

    def run(self, data: pd.DataFrame) -> CheckResult:
        return CheckResult(check_name=self.name, passed=True, summary="ok")


class _AlwaysFailCheck(ValidationCheck):
    @property
    def name(self) -> str:
        return "always_fail"

    def run(self, data: pd.DataFrame) -> CheckResult:
        return CheckResult(
            check_name=self.name,
            passed=False,
            total_issue_count=3,
            summary="always fails",
        )


def test_validator_runs_all_checks_and_aggregates_results() -> None:
    """DatasetValidator must run every injected check and preserve their order."""
    validator = DatasetValidator(checks=[_AlwaysPassCheck(), _AlwaysFailCheck()])
    report = validator.validate(pd.DataFrame({"a": [1, 2]}))

    assert len(report.results) == 2
    assert report.results[0].check_name == "always_pass"
    assert report.results[1].check_name == "always_fail"


def test_validator_overall_passed_is_false_if_any_check_fails() -> None:
    """overall_passed must be False when at least one check fails."""
    validator = DatasetValidator(checks=[_AlwaysPassCheck(), _AlwaysFailCheck()])
    report = validator.validate(pd.DataFrame({"a": [1]}))
    assert report.overall_passed is False


def test_validator_overall_passed_is_true_when_all_pass() -> None:
    """overall_passed must be True when every check passes."""
    validator = DatasetValidator(checks=[_AlwaysPassCheck()])
    report = validator.validate(pd.DataFrame({"a": [1]}))
    assert report.overall_passed is True


def test_validator_total_issue_count_sums_across_checks() -> None:
    """total_issue_count must sum total_issue_count across all checks."""
    validator = DatasetValidator(checks=[_AlwaysPassCheck(), _AlwaysFailCheck()])
    report = validator.validate(pd.DataFrame({"a": [1]}))
    assert report.total_issue_count == 3


def test_build_default_checks_returns_five_checks() -> None:
    """The factory must build the full standard set of checks."""
    checks = build_default_checks(ValidationSettings())
    names = {check.name for check in checks}
    assert names == {
        "missing_values",
        "duplicate_rows",
        "data_types",
        "gameweek_range",
        "player_identifiers",
    }


def test_default_checks_catch_issues_in_a_realistic_dirty_dataset() -> None:
    """End-to-end: the default check set must catch issues in a deliberately dirty dataset."""
    df = pd.DataFrame(
        {
            "season": ["2022-23", "2022-23", "2022-23", None],
            "name": ["Salah", "Salah", "Haaland", "Kane"],
            "GW": [1, 1, 39, 2],
            "total_points": [10, 10, "bad", 8],
        }
    )
    settings = ValidationSettings(
        required_columns=("season", "name"),
        duplicate_key_columns=("season", "name", "GW"),
        expected_numeric_columns=("total_points",),
        gameweek_columns=("GW", "round"),
        min_gameweek=1,
        max_gameweek=38,
        player_id_columns=("element", "name"),
    )
    validator = DatasetValidator(checks=build_default_checks(settings))
    report = validator.validate(df)

    assert report.overall_passed is False
    failed_checks = {r.check_name for r in report.results if not r.passed}
    assert "missing_values" in failed_checks
    assert "duplicate_rows" in failed_checks
    assert "data_types" in failed_checks
    assert "gameweek_range" in failed_checks


def test_write_markdown_report_produces_readable_file(tmp_path: Path) -> None:
    """write_markdown_report must produce a non-empty Markdown file with key sections."""
    validator = DatasetValidator(checks=[_AlwaysPassCheck(), _AlwaysFailCheck()])
    report = validator.validate(pd.DataFrame({"a": [1, 2, 3]}))

    report_path = tmp_path / "validation_report.md"
    write_markdown_report(report, report_path)

    text = report_path.read_text(encoding="utf-8")
    assert "Dataset Validation Report" in text
    assert "always_pass" in text
    assert "always_fail" in text
    assert "FAILED" in text
