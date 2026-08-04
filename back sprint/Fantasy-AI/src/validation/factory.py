"""Factory assembling the project's default set of validation checks.

Kept separate from :class:`~src.validation.validator.DatasetValidator`
so the validator itself never knows which concrete checks exist —
only this factory (and any caller who wants a custom set) does.
"""

from __future__ import annotations

from src.config.settings import ValidationSettings
from src.validation.checks.base import ValidationCheck
from src.validation.checks.data_types import DataTypeCheck
from src.validation.checks.duplicate_rows import DuplicateRowsCheck
from src.validation.checks.gameweek import GameweekCheck
from src.validation.checks.missing_values import MissingValuesCheck
from src.validation.checks.player_id import PlayerIdCheck


def build_default_checks(settings: ValidationSettings) -> list[ValidationCheck]:
    """Build the standard set of checks used by the Fantasy-AI validation pipeline.

    Args:
        settings: Validation settings controlling each check's rules.

    Returns:
        list[ValidationCheck]: The checks to run, in a sensible order
        (cheap/structural checks first, semantic checks last).
    """
    return [
        MissingValuesCheck(
            required_columns=settings.required_columns,
            max_issues_in_report=settings.max_issues_in_report,
        ),
        DuplicateRowsCheck(
            key_columns=settings.duplicate_key_columns,
            max_issues_in_report=settings.max_issues_in_report,
        ),
        DataTypeCheck(
            expected_numeric_columns=settings.expected_numeric_columns,
            max_issues_in_report=settings.max_issues_in_report,
        ),
        GameweekCheck(
            gameweek_columns=settings.gameweek_columns,
            min_gameweek=settings.min_gameweek,
            max_gameweek=settings.max_gameweek,
            max_issues_in_report=settings.max_issues_in_report,
        ),
        PlayerIdCheck(
            player_id_columns=settings.player_id_columns,
            max_issues_in_report=settings.max_issues_in_report,
        ),
    ]
