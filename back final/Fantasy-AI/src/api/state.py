"""Builds the API's application state once at startup.

Loading the engineered dataset and trained model, and computing
next-Gameweek predictions, are all relatively expensive — this module
does that work exactly once (at process startup) rather than per
request.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import Settings
from src.core.exceptions import FantasyAIError
from src.data_collection.services.team_mapping_service import TeamMappingService
from src.data_collection.sources.fpl_api_source import FPLApiDataSource
from src.metadata.player_metadata import PlayerMetadata, build_player_metadata
from src.metadata.team_metadata import TeamMetadata, build_team_metadata
from src.prediction.fixture_aware_next_gameweek import (
    ResolvedFixture,
    build_fixture_aware_next_gameweek_rows,
    resolve_team_fixtures,
)
from src.prediction.loader import LoadedModel, load_model
from src.prediction.predictor import PredictionService

logger = get_logger(__name__)


@dataclass
class AppState:
    """Everything the API's route handlers need, computed once at startup.

    Attributes:
        settings: The application settings used to build this state.
        engineered_data: The full engineered dataset (Sprint 5 output).
        loaded_model: The trained model and its reproducibility metadata.
        predictions: Next-Gameweek predictions for every player,
            including every engineered feature column (not just the
            trimmed CSV export columns), so services like the captain
            picker can filter on them. Enriched, where live metadata
            was reachable at startup, with real fixture data (Phase 3:
            ``opponent_team``, ``is_home``, ``fixture_difficulty``,
            ``fixture_source``) and presentation metadata (Phase 5:
            ``photo_url``, ``team_logo_url``, ``opponent_logo_url``).
        player_id_column: The resolved player identifier column name.
        live_metadata_available: Whether live fixture/metadata
            enrichment succeeded at startup. When ``False``,
            predictions still use the Sprint 7 proxy and lack the
            presentation-metadata columns — the API and frontend must
            handle their absence gracefully, never assume they exist.
    """

    settings: Settings
    engineered_data: pd.DataFrame
    loaded_model: LoadedModel
    predictions: pd.DataFrame
    player_id_column: str
    live_metadata_available: bool = False


def build_app_state(settings: Settings) -> AppState:
    """Load data and the trained model, and compute predictions, once.

    Args:
        settings: Application settings.

    Returns:
        AppState: The fully populated application state.

    Raises:
        FileNotFoundError: If the engineered dataset is missing.
        src.core.exceptions.ModelNotFoundError: If the model artifact
            or its metadata is missing.
        src.core.exceptions.PredictionError: If next-Gameweek rows
            cannot be built (e.g. no player identifier column).
    """
    features_path = settings.paths.processed_data_dir / "vaastav_features.csv"
    if not features_path.exists():
        raise FileNotFoundError(
            f"Engineered dataset not found at {features_path}. "
            "Run scripts.run_feature_engineering first."
        )

    logger.info("Loading engineered dataset from %s...", features_path)
    engineered_data = pd.read_csv(features_path, low_memory=False)

    model_path = settings.paths.models_dir / "best_model.joblib"
    metadata_path = settings.paths.models_dir / "best_model_metadata.json"
    loaded_model = load_model(model_path, metadata_path)

    player_id_column = next(
        (c for c in settings.feature_engineering.player_id_columns if c in engineered_data.columns),
        None,
    )
    if player_id_column is None:
        raise ValueError(
            f"No player identifier column found among "
            f"{settings.feature_engineering.player_id_columns}."
        )

    team_fixtures, team_metadata, player_metadata = _try_fetch_live_metadata(settings)
    live_metadata_available = bool(team_fixtures or team_metadata or player_metadata)

    next_gw_rows = build_fixture_aware_next_gameweek_rows(
        engineered_data,
        player_id_columns=settings.feature_engineering.player_id_columns,
        chronological_columns=settings.feature_engineering.chronological_columns,
        max_valid_gameweek=settings.prediction.max_valid_gameweek,
        team_fixtures=team_fixtures,
    )
    prediction_service = PredictionService(loaded_model)
    predictions = prediction_service.predict(next_gw_rows)

    predictions = _enrich_with_presentation_metadata(
        predictions,
        player_id_column=player_id_column,
        team_metadata=team_metadata,
        player_metadata=player_metadata,
    )

    logger.info(
        "API state ready: %d player(s), model '%s', live metadata available=%s.",
        len(predictions),
        loaded_model.model_name,
        live_metadata_available,
    )
    return AppState(
        settings=settings,
        engineered_data=engineered_data,
        loaded_model=loaded_model,
        predictions=predictions,
        player_id_column=player_id_column,
        live_metadata_available=live_metadata_available,
    )


def _try_fetch_live_metadata(
    settings: Settings,
) -> tuple[
    dict[str, ResolvedFixture] | None,
    dict[int, TeamMetadata] | None,
    dict[int, PlayerMetadata] | None,
]:
    """Best-effort fetch of live fixtures + team/player presentation metadata.

    Deliberately never raises: this enriches the experience (Phase 3
    fixture-awareness, Phase 5 photos/badges) but the API must remain
    fully functional (using the Sprint 7 proxy, no photos/badges) if
    the live FPL API is unreachable at startup.

    Args:
        settings: Application settings.

    Returns:
        tuple: ``(team_fixtures, team_metadata, player_metadata)``,
        each ``None``/empty if the fetch failed.
    """
    try:
        fpl_source = FPLApiDataSource(
            base_url=settings.data_sources.fpl_api_base_url,
            events_path=settings.automation.fpl_api_events_path,
            live_event_path_template=settings.automation.fpl_api_live_event_path_template,
            fixtures_path=settings.automation.fpl_api_fixtures_path,
            timeout_seconds=settings.data_sources.request_timeout_seconds,
            max_retries=settings.data_sources.request_max_retries,
        )
        live_dir = settings.paths.raw_data_dir / "fpl_api"
        if not (live_dir / "bootstrap_static.json").exists():
            fpl_source.download(live_dir)

        teams_raw = fpl_source.get_teams(live_dir)
        mapping_service = TeamMappingService(
            settings.paths.external_data_dir / settings.fixture_aware.team_mapping_cache_path
        )
        team_id_to_name = mapping_service.build_mapping(teams_raw)

        fixtures_raw = fpl_source.get_fixtures(future_only=True)
        team_fixtures = resolve_team_fixtures(fixtures_raw, team_id_to_name)

        team_metadata = build_team_metadata(teams_raw)
        bootstrap = json.loads((live_dir / "bootstrap_static.json").read_text(encoding="utf-8"))
        player_metadata = build_player_metadata(bootstrap.get("elements", []))

        return team_fixtures, team_metadata, player_metadata
    except (FantasyAIError, OSError, ValueError) as exc:
        logger.warning(
            "Live fixture/metadata enrichment unavailable at startup (%s); "
            "predictions will use the last-played-match proxy with no photos/badges.",
            exc,
        )
        return None, None, None


def _enrich_with_presentation_metadata(
    predictions: pd.DataFrame,
    player_id_column: str,
    team_metadata: dict[int, TeamMetadata] | None,
    player_metadata: dict[int, PlayerMetadata] | None,
) -> pd.DataFrame:
    """Add photo_url/team_logo_url/opponent_logo_url columns where resolvable.

    Args:
        predictions: The predictions DataFrame to enrich.
        player_id_column: Column identifying each player.
        team_metadata: Team-ID -> TeamMetadata, or None.
        player_metadata: Player-ID -> PlayerMetadata, or None.

    Returns:
        pd.DataFrame: The enriched predictions (new columns are all
        ``None`` when metadata wasn't available — never fabricated).
    """
    result = predictions.copy()
    result["photo_url"] = None
    result["team_logo_url"] = None
    result["opponent_logo_url"] = None

    if player_metadata:
        name_by_team_id = {}
        if team_metadata:
            name_by_team_id = {tm.name: tm.badge_url for tm in team_metadata.values()}

        def lookup_photo(pid: object) -> str | None:
            try:
                meta = player_metadata.get(int(pid))  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return None
            return meta.photo_url if meta else None

        result["photo_url"] = result[player_id_column].map(lookup_photo)

        if team_metadata and "team" in result.columns:
            result["team_logo_url"] = result["team"].map(name_by_team_id)
        if team_metadata and "opponent_team" in result.columns:
            result["opponent_logo_url"] = result["opponent_team"].map(name_by_team_id)

    return result
