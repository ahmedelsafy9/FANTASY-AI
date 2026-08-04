"""Factory assembling the project's default feature engineering pipeline.

Kept separate from :class:`~src.feature_engineering.pipeline.FeaturePipeline`
so the pipeline itself never knows which concrete steps exist — only
this factory (and any caller who wants a custom sequence) does.
"""

from __future__ import annotations

from src.config.settings import FeatureEngineeringSettings
from src.feature_engineering.models import RollingFeatureSpec
from src.feature_engineering.steps.base import FeatureStep
from src.feature_engineering.steps.form_index import FormIndexStep
from src.feature_engineering.steps.home_away import HomeAwayFlagStep
from src.feature_engineering.steps.price_trend import PriceTrendStep
from src.feature_engineering.steps.rest_days import RestDaysStep
from src.feature_engineering.steps.rolling_stats import RollingAverageStep
from src.feature_engineering.steps.team_strength import TeamStrengthStep


def build_default_feature_steps(settings: FeatureEngineeringSettings) -> list[FeatureStep]:
    """Build the standard feature engineering step sequence for Fantasy-AI.

    Covers every feature requested for Sprint 5: rolling averages over
    3/5/10-match windows for points, minutes, BPS, and ICT; rolling xG
    and xA; a home/away flag; rest days; team and opponent strength;
    price trend; and a composite form index.

    Step order matters: rolling averages must run before the form
    index (which consumes their output columns).

    Args:
        settings: Feature engineering settings controlling every
            column list, window, and weight used below.

    Returns:
        list[FeatureStep]: The steps to run, in order.
    """
    rolling_specs = (
        RollingFeatureSpec(
            output_name="total_points",
            source_candidates=settings.points_columns,
            windows=settings.rolling_windows,
        ),
        RollingFeatureSpec(
            output_name="minutes",
            source_candidates=settings.minutes_columns,
            windows=settings.rolling_windows,
        ),
        RollingFeatureSpec(
            output_name="bps",
            source_candidates=settings.bps_columns,
            windows=settings.rolling_windows,
        ),
        RollingFeatureSpec(
            output_name="ict_index",
            source_candidates=settings.ict_columns,
            windows=settings.rolling_windows,
        ),
        RollingFeatureSpec(
            output_name="xG",
            source_candidates=settings.xg_columns,
            windows=settings.rolling_windows,
        ),
        RollingFeatureSpec(
            output_name="xA",
            source_candidates=settings.xa_columns,
            windows=settings.rolling_windows,
        ),
    )

    form_index_components = tuple(
        f"total_points_avg_last_{w}" for w in settings.form_index_windows
    )

    return [
        RollingAverageStep(
            player_id_columns=settings.player_id_columns,
            chronological_columns=settings.chronological_columns,
            specs=rolling_specs,
        ),
        HomeAwayFlagStep(source_column=settings.home_column),
        RestDaysStep(
            player_id_columns=settings.player_id_columns,
            kickoff_time_column=settings.kickoff_time_column,
            default_rest_days=settings.default_rest_days,
        ),
        TeamStrengthStep(
            team_column=settings.team_column,
            opponent_column=settings.opponent_column,
            strength_source_column=settings.strength_source_column,
            chronological_columns=settings.chronological_columns,
        ),
        PriceTrendStep(
            player_id_columns=settings.player_id_columns,
            chronological_columns=settings.chronological_columns,
            value_column=settings.value_column,
            windows=settings.price_trend_windows,
        ),
        FormIndexStep(
            component_columns=form_index_components,
            weights=settings.form_index_weights,
        ),
    ]
