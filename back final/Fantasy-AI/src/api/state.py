"""Builds the API's application state once at startup.

Loading the engineered dataset and trained model, and computing
next-Gameweek predictions, are all relatively expensive — this module
does that work exactly once (at process startup) rather than per
request.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass

import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import Settings
from src.core.exceptions import FantasyAIError
from src.data_collection.services.team_mapping_service import TeamMappingService
from src.data_collection.sources.fpl_api_source import FPLApiDataSource
from src.metadata.player_metadata import PlayerMetadata, build_player_metadata, player_photo_url
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

    team_fixtures, team_metadata, player_metadata, current_bootstrap = _try_fetch_live_metadata(settings)
    live_metadata_available = bool(team_fixtures or team_metadata or player_metadata)

    next_gw_rows = build_fixture_aware_next_gameweek_rows(
        engineered_data,
        player_id_columns=settings.feature_engineering.player_id_columns,
        chronological_columns=settings.feature_engineering.chronological_columns,
        max_valid_gameweek=settings.prediction.max_valid_gameweek,
        team_fixtures=team_fixtures,
    )
    prediction_service = PredictionService(loaded_model)
    raw_predictions = prediction_service.predict(next_gw_rows)

    if current_bootstrap and "elements" in current_bootstrap and current_bootstrap["elements"]:
        predictions = _build_current_fpl_predictions(
            current_bootstrap=current_bootstrap,
            model_predictions=raw_predictions,
            player_id_column=player_id_column,
            team_metadata=team_metadata,
            player_metadata=player_metadata,
        )
    else:
        predictions = _enrich_with_presentation_metadata(
            raw_predictions,
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
    dict[str, Any] | None,
]:
    """Best-effort fetch of live fixtures + team/player presentation metadata.

    Deliberately never raises: this enriches the experience (Phase 3
    fixture-awareness, Phase 5 photos/badges) but the API must remain
    fully functional (using the Sprint 7 proxy, no photos/badges) if
    the live FPL API is unreachable at startup.

    Args:
        settings: Application settings.

    Returns:
        tuple: ``(team_fixtures, team_metadata, player_metadata, current_bootstrap)``,
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
        bootstrap = fpl_source.get_bootstrap_static(live_dir)
        player_metadata = build_player_metadata(bootstrap.get("elements", []))

        return team_fixtures, team_metadata, player_metadata, bootstrap
    except (FantasyAIError, OSError, ValueError) as exc:
        logger.warning(
            "Live fixture/metadata enrichment unavailable at startup (%s); "
            "predictions will use the last-played-match proxy with no photos/badges.",
            exc,
        )
        return None, None, None, None


def _build_current_fpl_predictions(
    current_bootstrap: dict[str, Any],
    model_predictions: pd.DataFrame,
    player_id_column: str,
    team_metadata: dict[int, TeamMetadata] | None,
    player_metadata: dict[int, PlayerMetadata] | None,
) -> pd.DataFrame:
    """Build the CURRENT prediction/squad pool driving dataset.

    The official FPL bootstrap-static endpoint (elements + teams) is the single
    source of truth for current players, teams, positions, prices, and status.

    Conceptually: CURRENT FPL PLAYERS (bootstrap["elements"]) LEFT JOIN MODEL PREDICTIONS.
    """
    elements = current_bootstrap.get("elements", [])
    teams = current_bootstrap.get("teams", [])
    team_names = {int(t["id"]): str(t.get("name", "")) for t in teams if "id" in t}

    predictions_by_id: dict[int, pd.Series] = {}
    predictions_by_name: dict[str, pd.Series] = {}

    for _, row in model_predictions.iterrows():
        pid = row.get(player_id_column) or row.get("element") or row.get("id")
        if pd.notna(pid):
            try:
                predictions_by_id[int(pid)] = row
            except (TypeError, ValueError):
                pass
        name_val = row.get("name") or row.get("name_normalized")
        if name_val:
            norm = _normalize_player_name(str(name_val))
            if norm and norm not in predictions_by_name:
                predictions_by_name[norm] = row

    rows: list[dict[str, Any]] = []
    for elem in elements:
        elem_id = elem.get("id")
        if elem_id is None:
            continue
        numeric_id = int(elem_id)

        fn = str(elem.get("first_name", "")).strip()
        sn = str(elem.get("second_name", "")).strip()
        web_name = str(elem.get("web_name", "Unknown"))
        full_name = f"{fn} {sn}".strip() if (fn or sn) else web_name
        team_id = elem.get("team")
        team_name = team_names.get(int(team_id), f"Team {team_id}") if team_id is not None else "Unknown"

        current_player_dict: dict[str, Any] = {
            player_id_column: numeric_id,
            "element": numeric_id,
            "id": numeric_id,
            "name": web_name,
            "first_name": fn,
            "second_name": sn,
            "full_name": full_name,
            "name_normalized": _normalize_player_name(full_name),
            "team": team_name,
            "team_id": team_id,
            "element_type": elem.get("element_type"),
            "now_cost": elem.get("now_cost"),
            "value": elem.get("now_cost"),
            "status": elem.get("status"),
            "total_points": elem.get("total_points"),
            "minutes": elem.get("minutes"),
            "goals_scored": elem.get("goals_scored"),
            "assists": elem.get("assists"),
            "clean_sheets": elem.get("clean_sheets"),
            "bonus": elem.get("bonus"),
            "influence": elem.get("influence"),
            "creativity": elem.get("creativity"),
            "threat": elem.get("threat"),
            "ict_index": elem.get("ict_index"),
            "photo_url": player_photo_url(elem.get("photo")),
        }

        if team_metadata and team_id is not None and int(team_id) in team_metadata:
            current_player_dict["team_logo_url"] = team_metadata[int(team_id)].badge_url
        else:
            current_player_dict["team_logo_url"] = None

        model_row = None
        if numeric_id in predictions_by_id:
            model_row = predictions_by_id[numeric_id]
        else:
            norm_full = current_player_dict["name_normalized"]
            norm_web = _normalize_player_name(web_name)
            if norm_full in predictions_by_name:
                model_row = predictions_by_name[norm_full]
            elif norm_web in predictions_by_name:
                model_row = predictions_by_name[norm_web]

        if model_row is not None:
            for col in model_row.index:
                if col not in current_player_dict:
                    current_player_dict[col] = model_row[col]
                elif col in ("predicted_total_points", "predicted_for_gw", "opponent_team", "is_home", "fixture_difficulty", "fixture_source"):
                    current_player_dict[col] = model_row[col]
        else:
            current_player_dict["predicted_total_points"] = 0.0
            current_player_dict["predicted_for_gw"] = 1
            current_player_dict["fixture_source"] = "no_historical_data"
            current_player_dict["opponent_team"] = None
            current_player_dict["is_home"] = 0
            current_player_dict["fixture_difficulty"] = None
            current_player_dict["opponent_logo_url"] = None

        rows.append(current_player_dict)

    return pd.DataFrame(rows)


def _normalize_player_name(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.lower().replace("-", " ").replace(".", "").replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


def _enrich_with_presentation_metadata(
    predictions: pd.DataFrame,
    player_id_column: str,
    team_metadata: dict[int, TeamMetadata] | None,
    player_metadata: dict[int, PlayerMetadata] | None,
) -> pd.DataFrame:
    """Add photo_url/team_logo_url/opponent_logo_url columns where resolvable.

    Matches players accurately by normalized name against official Premier League
    metadata so that players get their real photo and never a wrong face.

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

        # Build normalized name -> photo_url mapping
        photo_by_name: dict[str, str] = {}
        for meta in player_metadata.values():
            if not meta.photo_url:
                continue
            if meta.full_name:
                norm_full = _normalize_player_name(meta.full_name)
                if norm_full:
                    photo_by_name[norm_full] = meta.photo_url
            norm_web = _normalize_player_name(meta.web_name)
            if norm_web and norm_web not in photo_by_name:
                photo_by_name[norm_web] = meta.photo_url

        def lookup_photo(row: pd.Series) -> str | None:
            raw_name = row.get("name") or row.get("name_normalized")
            if not raw_name:
                return None
            norm_p = _normalize_player_name(str(raw_name))
            if norm_p in photo_by_name:
                return photo_by_name[norm_p]
            words = norm_p.split()
            if len(words) > 1:
                first_last = f"{words[0]} {words[-1]}"
                if first_last in photo_by_name:
                    return photo_by_name[first_last]
            for w in words:
                if len(w) >= 4 and w in photo_by_name:
                    return photo_by_name[w]
            return None

        result["photo_url"] = result.apply(lookup_photo, axis=1)

        if team_metadata and "team" in result.columns:
            result["team_logo_url"] = result["team"].map(name_by_team_id)
        if team_metadata and "opponent_team" in result.columns:
            result["opponent_logo_url"] = result["opponent_team"].map(name_by_team_id)

    return result
