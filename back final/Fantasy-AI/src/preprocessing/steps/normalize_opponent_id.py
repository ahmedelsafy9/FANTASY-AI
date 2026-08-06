"""Preprocessing step normalizing a numeric opponent-team-ID column to team names."""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.data_collection.services.team_mapping_service import resolve_numeric_opponent_column
from src.preprocessing.steps.base import PreprocessingStep, StepSummary

logger = get_logger(__name__)


class NormalizeOpponentIdStep(PreprocessingStep):
    """Resolves a numeric ``opponent_team`` column to team names via a mapping.

    This is the fix for the historically-logged
    ``"Skipping opponent_strength: 'team' and 'opponent_team' do not
    share a compatible value domain"`` warning: some seasons store
    ``opponent_team`` as a small integer team ID rather than a name.
    Given a team-ID -> name mapping (see
    :mod:`src.data_collection.services.team_mapping_service`), this step
    resolves those IDs to names so ``opponent_team`` shares the same
    domain as ``team``, which downstream feature engineering
    (``TeamStrengthStep``) requires for its join.

    If no mapping is available (e.g. offline, or the live API is
    unreachable), this step is a documented no-op — it does not guess
    or silently fabricate team names.

    Args:
        opponent_column: Column to normalize.
        team_id_mapping: Team ID -> team name mapping. An empty or
            ``None`` mapping makes this step a no-op.
    """

    def __init__(self, opponent_column: str, team_id_mapping: dict[int, str] | None) -> None:
        self._opponent_column = opponent_column
        self._team_id_mapping = team_id_mapping or {}

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "normalize_opponent_id"

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, StepSummary]:
        """Resolve numeric opponent-team IDs to team names where a mapping exists.

        Args:
            data: The DataFrame to normalize.

        Returns:
            tuple[pd.DataFrame, StepSummary]: The normalized data and a
            summary of how many values were resolved.
        """
        rows_before = len(data)
        cleaned = data.copy()

        if self._opponent_column not in cleaned.columns:
            description = f"Column '{self._opponent_column}' not present; no-op."
            logger.info(description)
            return cleaned, StepSummary(
                step_name=self.name, rows_before=rows_before, rows_after=rows_before,
                description=description,
            )

        if not self._team_id_mapping:
            description = "No team ID mapping available; opponent_team left as-is."
            logger.warning(description)
            return cleaned, StepSummary(
                step_name=self.name, rows_before=rows_before, rows_after=rows_before,
                description=description,
            )

        resolved, mapped_count = resolve_numeric_opponent_column(
            cleaned, self._opponent_column, self._team_id_mapping
        )
        cleaned[self._opponent_column] = resolved

        description = (
            f"Resolved {mapped_count} numeric value(s) in '{self._opponent_column}' "
            f"to team names using a {len(self._team_id_mapping)}-team mapping."
        )
        logger.info(description)

        return cleaned, StepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(cleaned),
            description=description,
        )
