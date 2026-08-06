"""Factory assembling the project's default preprocessing pipeline.

Kept separate from :class:`~src.preprocessing.pipeline.PreprocessingPipeline`
so the pipeline itself never knows which concrete steps exist — only
this factory (and any caller who wants a custom sequence) does.
"""

from __future__ import annotations

from pathlib import Path

from src.config.settings import PreprocessingSettings, ValidationSettings
from src.preprocessing.steps.base import PreprocessingStep
from src.preprocessing.steps.convert_types import ConvertTypesStep
from src.preprocessing.steps.dedupe import DropDuplicatesStep
from src.preprocessing.steps.drop_invalid_required import DropInvalidRequiredRowsStep
from src.preprocessing.steps.fill_missing import FillMissingValuesStep
from src.preprocessing.steps.normalize_names import NormalizeNamesStep
from src.preprocessing.steps.normalize_opponent_id import NormalizeOpponentIdStep
from src.preprocessing.steps.resolve_opponent_from_fixture import ResolveOpponentFromFixtureStep


def build_default_pipeline_steps(
    preprocessing_settings: PreprocessingSettings,
    validation_settings: ValidationSettings,
    team_id_mapping: dict[int, str] | None = None,
    opponent_column: str = "opponent_team",
    vaastav_data_dir: Path | None = None,
) -> list[PreprocessingStep]:
    """Build the standard preprocessing step sequence for Fantasy-AI.

    The step order matters: names (and opponent-team IDs) are normalized
    first so that whitespace/Unicode/ID-domain differences don't hide
    true duplicates from the deduplication step or break downstream
    joins; duplicates and unsalvageable rows are removed next; types are
    converted after that; and missing-value filling runs last (so it
    only fills genuinely-missing cells in otherwise clean, correctly-
    typed columns).

    Fixture-based opponent resolution runs before the ID-based fallback:
    it uses the ``(season, fixture)`` relationship to derive the
    opponent from the two teams involved in each fixture — this is
    authoritative for historical data where numeric ``opponent_team``
    IDs may not be stable across seasons.  When ``vaastav_data_dir``
    is provided, the step also loads per-season reference files
    (``teams.csv``, ``fixtures.csv``, ``players_raw.csv``) to populate
    the ``team`` column and resolve opponents for older seasons where
    the ``team`` column is absent from the merged dataset.  The ID-based
    ``NormalizeOpponentIdStep`` then handles any remaining numeric
    values (e.g. current-season / live data).

    Args:
        preprocessing_settings: Settings controlling cleaning rules.
        validation_settings: Reused for the required-column and
            duplicate-key column lists, so the same notion of
            "required" and "duplicate key" is shared between the
            validation and preprocessing layers.
        team_id_mapping: Optional team-ID -> team-name mapping (see
            :mod:`src.data_collection.services.team_mapping_service`).
            When provided, a numeric ``opponent_team`` column is
            resolved to team names, fixing the opponent-strength
            domain-mismatch issue. Omitted (``None``) by default so
            existing callers remain unaffected until they opt in.
        opponent_column: Column to normalize when a mapping is provided.
        vaastav_data_dir: Optional path to the extracted Vaastav
            repository's ``data/`` directory containing per-season
            subdirectories with reference files. When ``None``, the
            step auto-detects the default location.

    Returns:
        list[PreprocessingStep]: The steps to run, in order.
    """
    return [
        NormalizeNamesStep(name_columns=preprocessing_settings.name_columns),
        ResolveOpponentFromFixtureStep(
            season_column="season",
            fixture_column="fixture",
            team_column="team",
            opponent_column=opponent_column,
            vaastav_data_dir=vaastav_data_dir,
        ),
        NormalizeOpponentIdStep(opponent_column=opponent_column, team_id_mapping=team_id_mapping),
        DropDuplicatesStep(key_columns=validation_settings.duplicate_key_columns),
        DropInvalidRequiredRowsStep(required_columns=validation_settings.required_columns),
        ConvertTypesStep(
            integer_columns=preprocessing_settings.integer_columns,
            float_columns=preprocessing_settings.float_columns,
            boolean_columns=preprocessing_settings.boolean_columns,
            datetime_columns=preprocessing_settings.datetime_columns,
        ),
        FillMissingValuesStep(zero_fill_columns=preprocessing_settings.zero_fill_columns),
    ]

