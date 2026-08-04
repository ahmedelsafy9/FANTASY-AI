"""Factory assembling the project's default preprocessing pipeline.

Kept separate from :class:`~src.preprocessing.pipeline.PreprocessingPipeline`
so the pipeline itself never knows which concrete steps exist — only
this factory (and any caller who wants a custom sequence) does.
"""

from __future__ import annotations

from src.config.settings import PreprocessingSettings, ValidationSettings
from src.preprocessing.steps.base import PreprocessingStep
from src.preprocessing.steps.convert_types import ConvertTypesStep
from src.preprocessing.steps.dedupe import DropDuplicatesStep
from src.preprocessing.steps.drop_invalid_required import DropInvalidRequiredRowsStep
from src.preprocessing.steps.fill_missing import FillMissingValuesStep
from src.preprocessing.steps.normalize_names import NormalizeNamesStep


def build_default_pipeline_steps(
    preprocessing_settings: PreprocessingSettings,
    validation_settings: ValidationSettings,
) -> list[PreprocessingStep]:
    """Build the standard preprocessing step sequence for Fantasy-AI.

    The step order matters: names are normalized first so that
    whitespace/Unicode differences don't hide true duplicates from the
    deduplication step; duplicates and unsalvageable rows are removed
    next; types are converted after that; and missing-value filling
    runs last (so it only fills genuinely-missing cells in otherwise
    clean, correctly-typed columns).

    Args:
        preprocessing_settings: Settings controlling cleaning rules.
        validation_settings: Reused for the required-column and
            duplicate-key column lists, so the same notion of
            "required" and "duplicate key" is shared between the
            validation and preprocessing layers.

    Returns:
        list[PreprocessingStep]: The steps to run, in order.
    """
    return [
        NormalizeNamesStep(name_columns=preprocessing_settings.name_columns),
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
