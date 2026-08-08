"""Builds the API's application state once at startup.

Loading the engineered dataset and trained model, and computing
next-Gameweek predictions, are all relatively expensive — this module
does that work exactly once (at process startup) rather than per
request.

Live FPL bootstrap data is also used to ensure that the prediction
pool only contains players and teams that actually exist in the
current season.
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
    """Everything the API's route handlers need, computed once at startup."""

    settings: Settings
    engineered_data: pd.DataFrame
    loaded_model: LoadedModel
    predictions: pd.DataFrame
    player_id_column: str
    live_metadata_available: bool = False


def build_app_state(settings: Settings) -> AppState:
    """Load data, model, live FPL metadata and compute predictions once."""

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
        (
            c
            for c in settings.feature_engineering.player_id_columns
            if c in engineered_data.columns
        ),
        None,
    )

    if player_id_column is None:
        raise ValueError(
            f"No player identifier column found among "
            f"{settings.feature_engineering.player_id_columns}."
        )

<<<<<<< HEAD
    team_fixtures, team_metadata, player_metadata, current_bootstrap = _try_fetch_live_metadata(settings)
    live_metadata_available = bool(team_fixtures or team_metadata or player_metadata)
=======
    # ---------------------------------------------------------------
    # Live FPL metadata
    # ---------------------------------------------------------------

    (
        team_fixtures,
        team_metadata,
        player_metadata,
        upcoming_team_fixtures,
    ) = _try_fetch_live_metadata(settings)

    live_metadata_available = bool(
        team_fixtures or team_metadata or player_metadata
    )

    # ---------------------------------------------------------------
    # Build next-gameweek prediction rows
    # ---------------------------------------------------------------
>>>>>>> 6a9fdc0c2339f3fbf5f47193d150e0596c75f4b7

    next_gw_rows = build_fixture_aware_next_gameweek_rows(
        engineered_data,
        player_id_columns=settings.feature_engineering.player_id_columns,
        chronological_columns=settings.feature_engineering.chronological_columns,
        max_valid_gameweek=settings.prediction.max_valid_gameweek,
        team_fixtures=team_fixtures,
    )

    prediction_service = PredictionService(loaded_model)
<<<<<<< HEAD
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
=======

    predictions = prediction_service.predict(next_gw_rows)

    # ---------------------------------------------------------------
    # IMPORTANT:
    # Use official FPL API bootstrap-static as the authority for the
    # CURRENT player pool (players, teams, positions, prices, status).
    #
    # Merge current FPL players with model predictions via a LEFT JOIN.
    # ---------------------------------------------------------------

    predictions = _build_current_fpl_prediction_pool(
        predictions=predictions,
        player_id_column=player_id_column,
        team_fixtures=team_fixtures,
        team_metadata=team_metadata,
        player_metadata=player_metadata,
        upcoming_team_fixtures=upcoming_team_fixtures,
    )
>>>>>>> 6a9fdc0c2339f3fbf5f47193d150e0596c75f4b7

    logger.info(
        "API state ready: %d current-season player(s), model '%s', "
        "live metadata available=%s.",
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


from src.prediction.fixture_aware_next_gameweek import (
    ResolvedFixture,
    UpcomingFixture,
    build_fixture_aware_next_gameweek_rows,
    resolve_team_fixtures,
    resolve_team_upcoming_fixtures,
)


def _try_fetch_live_metadata(
    settings: Settings,
) -> tuple[
    dict[str, ResolvedFixture] | None,
    dict[int, TeamMetadata] | None,
    dict[int, PlayerMetadata] | None,
<<<<<<< HEAD
    dict[str, Any] | None,
=======
    dict[str, list[UpcomingFixture]] | None,
>>>>>>> 6a9fdc0c2339f3fbf5f47193d150e0596c75f4b7
]:
    """Best-effort fetch of live fixtures + current FPL metadata."""

<<<<<<< HEAD
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
=======
>>>>>>> 6a9fdc0c2339f3fbf5f47193d150e0596c75f4b7
    try:
        fpl_source = FPLApiDataSource(
            base_url=settings.data_sources.fpl_api_base_url,
            events_path=settings.automation.fpl_api_events_path,
            live_event_path_template=(
                settings.automation.fpl_api_live_event_path_template
            ),
            fixtures_path=settings.automation.fpl_api_fixtures_path,
            timeout_seconds=settings.data_sources.request_timeout_seconds,
            max_retries=settings.data_sources.request_max_retries,
        )

        live_dir = settings.paths.raw_data_dir / "fpl_api"

        if not (live_dir / "bootstrap_static.json").exists():
            fpl_source.download(live_dir)

        teams_raw = fpl_source.get_teams(live_dir)

        mapping_service = TeamMappingService(
            settings.paths.external_data_dir
            / settings.fixture_aware.team_mapping_cache_path
        )

        team_id_to_name = mapping_service.build_mapping(teams_raw)

        fixtures_raw = fpl_source.get_fixtures(future_only=True)

        team_fixtures = resolve_team_fixtures(
            fixtures_raw,
            team_id_to_name,
        )

        team_metadata = build_team_metadata(teams_raw)
<<<<<<< HEAD
        bootstrap = fpl_source.get_bootstrap_static(live_dir)
        player_metadata = build_player_metadata(bootstrap.get("elements", []))

        return team_fixtures, team_metadata, player_metadata, bootstrap
=======

        upcoming_team_fixtures = resolve_team_upcoming_fixtures(
            fixtures_raw,
            team_id_to_name,
            team_metadata=team_metadata,
            max_fixtures=5,
        )

        bootstrap_path = live_dir / "bootstrap_static.json"

        bootstrap = json.loads(
            bootstrap_path.read_text(encoding="utf-8")
        )

        player_metadata = build_player_metadata(
            bootstrap.get("elements", [])
        )

        return (
            team_fixtures,
            team_metadata,
            player_metadata,
            upcoming_team_fixtures,
        )

>>>>>>> 6a9fdc0c2339f3fbf5f47193d150e0596c75f4b7
    except (FantasyAIError, OSError, ValueError) as exc:
        logger.warning(
            "Live fixture/metadata enrichment unavailable at startup "
            "(%s); predictions will use the available historical data.",
            exc,
        )
<<<<<<< HEAD
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
=======

        return None, None, None, None
>>>>>>> 6a9fdc0c2339f3fbf5f47193d150e0596c75f4b7


from src.preprocessing.steps.normalize_names import _fold_to_ascii_lower


def _build_current_fpl_prediction_pool(
    predictions: pd.DataFrame,
    player_id_column: str,
    team_fixtures: dict[str, ResolvedFixture] | None,
    team_metadata: dict[int, TeamMetadata] | None,
    player_metadata: dict[int, PlayerMetadata] | None,
    upcoming_team_fixtures: dict[str, list[UpcomingFixture]] | None = None,
) -> pd.DataFrame:
    """Build the active prediction pool using bootstrap-static as the authority.

    Conceptually performs:
        current_fpl_players LEFT JOIN model_predictions

    The current player pool, team names, positions, prices, status, and IDs
    are sourced directly from bootstrap-static (via player_metadata and team_metadata).
    Model predictions and historical feature columns are left-joined on stable
    player identity (``name_normalized``).

    If live metadata is unavailable, returns predictions unchanged as fallback.
    """
    if not player_metadata or not team_metadata:
        logger.warning(
            "Live FPL metadata unavailable; using historical predictions as fallback."
        )
        fallback_df = predictions.copy()
        for col in ("photo_url", "team_logo_url", "opponent_logo_url"):
            if col not in fallback_df.columns:
                fallback_df[col] = None
        if "upcoming_fixtures" not in fallback_df.columns:
            fallback_df["upcoming_fixtures"] = [[] for _ in range(len(fallback_df))]
        return fallback_df

    # 1. Determine stable join column in predictions DataFrame
    join_col = next(
        (c for c in ("name_normalized", "name") if c in predictions.columns),
        None,
    )

    # 2. Build DataFrame of current FPL players from bootstrap-static
    rows = []
    badge_by_team_name = {
        metadata.name: metadata.badge_url for metadata in team_metadata.values()
    }

    # Count occurrences of normalized names in current API to detect ambiguity
    norm_name_counts: dict[str, int] = {}
    for meta in player_metadata.values():
        full_name = f"{meta.first_name or ''} {meta.second_name or ''}".strip()
        norm_full = str(_fold_to_ascii_lower(full_name)) if full_name else ""
        if norm_full:
            norm_name_counts[norm_full] = norm_name_counts.get(norm_full, 0) + 1

    for player_id, meta in player_metadata.items():
        team_name = (
            team_metadata[meta.team_id].name
            if meta.team_id is not None and meta.team_id in team_metadata
            else "Unknown"
        )
        team_badge = (
            team_metadata[meta.team_id].badge_url
            if meta.team_id is not None and meta.team_id in team_metadata
            else None
        )

        full_name = f"{meta.first_name or ''} {meta.second_name or ''}".strip()
        norm_full = str(_fold_to_ascii_lower(full_name)) if full_name else ""
        norm_web = str(_fold_to_ascii_lower(meta.web_name)) if meta.web_name else ""

        # Flag ambiguous name match if multiple current players share the exact same normalized full name
        is_ambiguous = norm_full and norm_name_counts.get(norm_full, 0) > 1

        upcoming_list = (
            upcoming_team_fixtures.get(team_name)
            if upcoming_team_fixtures
            else None
        )
        upcoming_fixtures_payload = (
            [uf.to_dict() for uf in upcoming_list] if upcoming_list else []
        )

        row = {
            player_id_column: meta.player_id,
            "id": meta.player_id,
            "element": meta.player_id,
            "web_name": meta.web_name,
            "name": meta.web_name,
            "first_name": meta.first_name,
            "second_name": meta.second_name,
            "team_id": meta.team_id,
            "team": team_name,
            "element_type": meta.element_type,
            "position": meta.position,
            "now_cost": meta.now_cost,
            "value": meta.value,
            "status": meta.status,
            "photo_url": meta.photo_url,
            "team_logo_url": team_badge,
            "upcoming_fixtures": upcoming_fixtures_payload,
            "_norm_full": norm_full,
            "_norm_web": norm_web,
            "_is_ambiguous": is_ambiguous,
        }

        # Resolve upcoming fixture for this player's current team
        fixture = team_fixtures.get(team_name) if team_fixtures else None
        if fixture is not None:
            row["predicted_for_gw"] = fixture.gameweek
            row["opponent_team"] = fixture.opponent
            row["is_home"] = int(fixture.is_home)
            row["fixture_difficulty"] = fixture.difficulty
            row["fixture_source"] = "real_fixture"
            row["opponent_logo_url"] = badge_by_team_name.get(fixture.opponent)
        else:
            row["fixture_source"] = "proxy_last_played"
            row["fixture_difficulty"] = None
            row["opponent_logo_url"] = None

        rows.append(row)

    current_fpl_df = pd.DataFrame(rows)

    # 3. Join model_predictions by stable player identity (name_normalized)
    if join_col and not predictions.empty:
        pred_copy = predictions.copy()

        # Build a lookup dictionary from predictions by normalized name
        # Exclude metadata columns that are strictly driven by current bootstrap-static
        override_cols = {
            "team",
            "name",
            "web_name",
            "first_name",
            "second_name",
            "team_id",
            "element_type",
            "position",
            "now_cost",
            "value",
            "status",
            "photo_url",
            "team_logo_url",
            "opponent_logo_url",
            "predicted_for_gw",
            "opponent_team",
            "is_home",
            "fixture_difficulty",
            "fixture_source",
            "element",
            "id",
        }
        pred_cols = [c for c in pred_copy.columns if c == join_col or c not in override_cols]
        pred_subset = pred_copy[pred_cols].drop_duplicates(subset=[join_col])

        # Map predictions to current players using _norm_full or _norm_web
        # If a current player is ambiguous or has no historical match, model outputs remain None
        merged_rows = []
        pred_lookup = pred_subset.set_index(join_col).to_dict(orient="index")

        for _, c_row in current_fpl_df.iterrows():
            c_dict = c_row.to_dict()
            norm_full = c_dict.pop("_norm_full")
            norm_web = c_dict.pop("_norm_web")
            is_ambiguous = c_dict.pop("_is_ambiguous")

            matched_pred = None
            if not is_ambiguous:
                if norm_full in pred_lookup:
                    matched_pred = pred_lookup[norm_full]
                elif norm_web in pred_lookup:
                    matched_pred = pred_lookup[norm_web]

            if matched_pred:
                c_dict.update(matched_pred)

            merged_rows.append(c_dict)

        merged = pd.DataFrame(merged_rows)
    else:
        # Drop temporary normalization columns if join_col unavailable
        current_fpl_df = current_fpl_df.drop(
            columns=["_norm_full", "_norm_web", "_is_ambiguous"], errors="ignore"
        )
        merged = current_fpl_df

    # Ensure prediction target columns exist and are None for unmatched current players
    pred_target_cols = [
        c for c in merged.columns if c.startswith("predicted_") and not c.startswith("predicted_for_gw")
    ]
    for ptc in pred_target_cols:
        merged[ptc] = merged[ptc].astype(object).where(merged[ptc].notna(), None)

    logger.info(
        "Built current FPL prediction pool: %d active player(s) from API (merged on stable player identity).",
        len(merged),
    )
    return merged.reset_index(drop=True)