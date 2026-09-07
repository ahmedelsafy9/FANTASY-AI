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
from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.config.logging_config import get_logger
from src.config.settings import Settings
from src.core.exceptions import FantasyAIError
from src.data_collection.services.team_mapping_service import TeamMappingService
from src.data_collection.sources.fpl_api_source import FPLApiDataSource
from src.metadata.player_metadata import (
    PlayerMetadata,
    build_player_metadata,
)
from src.metadata.team_metadata import (
    TeamMetadata,
    build_team_metadata,
)
from src.prediction.fixture_aware_next_gameweek import (
    ResolvedFixture,
    UpcomingFixture,
    build_fixture_aware_next_gameweek_rows,
    resolve_team_fixtures,
    resolve_team_upcoming_fixtures,
)
from src.prediction.loader import LoadedModel, load_model
from src.prediction.predictor import PredictionService
from src.preprocessing.steps.normalize_names import _fold_to_ascii_lower


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
    season: str | None = None
    latest_completed_gameweek: int | None = None
    predicted_gameweek: int | None = None
    generated_at: str | None = None


def build_app_state(settings: Settings) -> AppState:
    """Load data, model, live FPL metadata and serve predictions."""

    features_path = (
        settings.paths.processed_data_dir / "vaastav_features.csv"
    )

    if not features_path.exists():
        raise FileNotFoundError(
            f"Engineered dataset not found at {features_path}. "
            "Run scripts.run_feature_engineering first."
        )

    logger.info(
        "Loading engineered dataset from %s...",
        features_path,
    )

    engineered_data = pd.read_csv(
        features_path,
        low_memory=False,
    )

    model_path = settings.paths.models_dir / "best_model.joblib"
    metadata_path = (
        settings.paths.models_dir / "best_model_metadata.json"
    )

    loaded_model = load_model(
        model_path,
        metadata_path,
    )

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
            "No player identifier column found among "
            f"{settings.feature_engineering.player_id_columns}."
        )

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
    # Authoritative Predictions: load Feedback 5 artifact if present
    # ---------------------------------------------------------------
    feedback5_path = settings.paths.processed_data_dir / "predictions_feedback5.csv"
    feedback5_meta_path = settings.paths.processed_data_dir / "predictions_feedback5_metadata.json"

    season = None
    latest_completed_gw = None
    predicted_gw = None
    generated_at = None

    if feedback5_meta_path.exists():
        try:
            fb5_meta = json.loads(feedback5_meta_path.read_text(encoding="utf-8"))
            season = fb5_meta.get("season")
            latest_completed_gw = fb5_meta.get("latest_completed_gameweek")
            predicted_gw = fb5_meta.get("predicted_gameweek")
            generated_at = fb5_meta.get("generated_at")
        except Exception as exc:
            logger.warning("Could not read feedback5 metadata: %s", exc)

    if season is None and "season" in engineered_data.columns:
        season = str(sorted(engineered_data["season"].dropna().unique())[-1])

    if latest_completed_gw is None:
        from src.prediction.next_gameweek import find_latest_completed_gameweek
        s_data = (
            engineered_data[engineered_data["season"] == season]
            if season and "season" in engineered_data.columns
            else engineered_data
        )
        latest_completed_gw = find_latest_completed_gameweek(s_data)

    if predicted_gw is None and latest_completed_gw is not None:
        predicted_gw = min(int(latest_completed_gw) + 1, settings.prediction.max_valid_gameweek)

    if feedback5_path.exists():
        logger.info(
            "Serving authoritative Feedback 5 predictions from %s...",
            feedback5_path,
        )
        fb5_df = pd.read_csv(feedback5_path, low_memory=False)
        if "predicted_total_points" not in fb5_df.columns and "predicted_expected_points" in fb5_df.columns:
            fb5_df["predicted_total_points"] = fb5_df["predicted_expected_points"]
        if "ceiling_p85" in fb5_df.columns and "predicted_p85_points" not in fb5_df.columns:
            fb5_df["predicted_p85_points"] = fb5_df["ceiling_p85"]
        if "ceiling_p90" in fb5_df.columns and "predicted_p90_points" not in fb5_df.columns:
            fb5_df["predicted_p90_points"] = fb5_df["ceiling_p90"]
        if "ceiling_p75" in fb5_df.columns and "predicted_p75_points" not in fb5_df.columns:
            fb5_df["predicted_p75_points"] = fb5_df["ceiling_p75"]
        if "predicted_fpl_rank_score" in fb5_df.columns and "captaincy_score" not in fb5_df.columns:
            fb5_df["captaincy_score"] = fb5_df["predicted_fpl_rank_score"]
        predictions = fb5_df
    else:
        logger.info(
            "Feedback 5 prediction artifact not found; falling back to model prediction..."
        )
        next_gw_rows = build_fixture_aware_next_gameweek_rows(
            engineered_data,
            player_id_columns=settings.feature_engineering.player_id_columns,
            chronological_columns=settings.feature_engineering.chronological_columns,
            max_valid_gameweek=settings.prediction.max_valid_gameweek,
            team_fixtures=team_fixtures,
        )
        prediction_service = PredictionService(loaded_model)
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

    logger.info(
        "API state ready: %d current-season player(s), model '%s', "
        "live metadata available=%s, season=%s, completed_gw=%s, target_gw=%s.",
        len(predictions),
        loaded_model.model_name,
        live_metadata_available,
        season,
        latest_completed_gw,
        predicted_gw,
    )

    return AppState(
        settings=settings,
        engineered_data=engineered_data,
        loaded_model=loaded_model,
        predictions=predictions,
        player_id_column=player_id_column,
        live_metadata_available=live_metadata_available,
        season=season,
        latest_completed_gameweek=latest_completed_gw,
        predicted_gameweek=predicted_gw,
        generated_at=generated_at,
    )


def _try_fetch_live_metadata(
    settings: Settings,
) -> tuple[
    dict[str, ResolvedFixture] | None,
    dict[int, TeamMetadata] | None,
    dict[int, PlayerMetadata] | None,
    dict[str, list[UpcomingFixture]] | None,
]:
    """Best-effort fetch of live fixtures + current FPL metadata.

    Deliberately never raises: this enriches the experience
    (fixture-awareness, photos/badges, and upcoming fixtures), but the
    API must remain fully functional if the live FPL API is unreachable
    at startup.
    """

    try:
        fpl_source = FPLApiDataSource(
            base_url=settings.data_sources.fpl_api_base_url,
            events_path=settings.automation.fpl_api_events_path,
            live_event_path_template=(
                settings.automation.fpl_api_live_event_path_template
            ),
            fixtures_path=settings.automation.fpl_api_fixtures_path,
            timeout_seconds=(
                settings.data_sources.request_timeout_seconds
            ),
            max_retries=(
                settings.data_sources.request_max_retries
            ),
        )

        live_dir = settings.paths.raw_data_dir / "fpl_api"

        if not (live_dir / "bootstrap_static.json").exists():
            fpl_source.download(live_dir)

        teams_raw = fpl_source.get_teams(live_dir)

        mapping_service = TeamMappingService(
            settings.paths.external_data_dir
            / settings.fixture_aware.team_mapping_cache_path
        )

        team_id_to_name = mapping_service.build_mapping(
            teams_raw
        )

        fixtures_raw = fpl_source.get_fixtures(
            future_only=True
        )

        team_fixtures = resolve_team_fixtures(
            fixtures_raw,
            team_id_to_name,
        )

        team_metadata = build_team_metadata(
            teams_raw
        )

        upcoming_team_fixtures = resolve_team_upcoming_fixtures(
            fixtures_raw,
            team_id_to_name,
            team_metadata=team_metadata,
            max_fixtures=5,
        )

        bootstrap_path = live_dir / "bootstrap_static.json"

        bootstrap = json.loads(
            bootstrap_path.read_text(
                encoding="utf-8"
            )
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

    except (
        FantasyAIError,
        OSError,
        ValueError,
    ) as exc:
        logger.warning(
            "Live fixture/metadata enrichment unavailable at startup "
            "(%s); predictions will use the available historical data.",
            exc,
        )

        return None, None, None, None


def _build_current_fpl_prediction_pool(
    predictions: pd.DataFrame,
    player_id_column: str,
    team_fixtures: dict[str, ResolvedFixture] | None,
    team_metadata: dict[int, TeamMetadata] | None,
    player_metadata: dict[int, PlayerMetadata] | None,
    upcoming_team_fixtures: (
        dict[str, list[UpcomingFixture]] | None
    ) = None,
) -> pd.DataFrame:
    """Build the active prediction pool using bootstrap-static as authority.

    Conceptually performs:

        current_fpl_players LEFT JOIN model_predictions

    The current player pool, team names, positions, prices, status,
    and IDs are sourced directly from bootstrap-static via
    player_metadata and team_metadata.

    Model predictions and historical feature columns are left-joined
    on stable player identity.

    If live metadata is unavailable, returns predictions unchanged
    as fallback.
    """

    if not player_metadata or not team_metadata:
        logger.warning(
            "Live FPL metadata unavailable; "
            "using historical predictions as fallback."
        )

        fallback_df = predictions.copy()

        for col in (
            "photo_url",
            "team_logo_url",
            "opponent_logo_url",
        ):
            if col not in fallback_df.columns:
                fallback_df[col] = None

        if "upcoming_fixtures" not in fallback_df.columns:
            fallback_df["upcoming_fixtures"] = [
                []
                for _ in range(len(fallback_df))
            ]

        return fallback_df

    # ---------------------------------------------------------------
    # 1. Determine stable join column in predictions DataFrame
    # ---------------------------------------------------------------

    join_col = next(
        (
            c
            for c in (
                "name_normalized",
                "name",
            )
            if c in predictions.columns
        ),
        None,
    )

    # ---------------------------------------------------------------
    # 2. Build DataFrame of current FPL players
    # ---------------------------------------------------------------

    rows: list[dict[str, Any]] = []

    badge_by_team_name = {
        metadata.name: metadata.badge_url
        for metadata in team_metadata.values()
    }

    # Count occurrences of normalized names in current API
    # to detect ambiguous player names.
    norm_name_counts: dict[str, int] = {}

    for meta in player_metadata.values():
        full_name = (
            f"{meta.first_name or ''} "
            f"{meta.second_name or ''}"
        ).strip()

        norm_full = (
            str(_fold_to_ascii_lower(full_name))
            if full_name
            else ""
        )

        if norm_full:
            norm_name_counts[norm_full] = (
                norm_name_counts.get(norm_full, 0) + 1
            )

    for player_id, meta in player_metadata.items():
        team_name = (
            team_metadata[meta.team_id].name
            if (
                meta.team_id is not None
                and meta.team_id in team_metadata
            )
            else "Unknown"
        )

        team_badge = (
            team_metadata[meta.team_id].badge_url
            if (
                meta.team_id is not None
                and meta.team_id in team_metadata
            )
            else None
        )

        full_name = (
            f"{meta.first_name or ''} "
            f"{meta.second_name or ''}"
        ).strip()

        norm_full = (
            str(_fold_to_ascii_lower(full_name))
            if full_name
            else ""
        )

        norm_web = (
            str(_fold_to_ascii_lower(meta.web_name))
            if meta.web_name
            else ""
        )

        # Flag ambiguous name match if multiple current players
        # share the exact same normalized full name.
        is_ambiguous = (
            bool(norm_full)
            and norm_name_counts.get(norm_full, 0) > 1
        )

        upcoming_list = (
            upcoming_team_fixtures.get(team_name)
            if upcoming_team_fixtures
            else None
        )

        upcoming_fixtures_payload = (
            [
                uf.to_dict()
                for uf in upcoming_list
            ]
            if upcoming_list
            else []
        )

        row: dict[str, Any] = {
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

        # -----------------------------------------------------------
        # Resolve upcoming fixture for player's current team
        # -----------------------------------------------------------

        fixture = (
            team_fixtures.get(team_name)
            if team_fixtures
            else None
        )

        if fixture is not None:
            row["predicted_for_gw"] = fixture.gameweek
            row["opponent_team"] = fixture.opponent
            row["is_home"] = int(fixture.is_home)
            row["fixture_difficulty"] = fixture.difficulty
            row["fixture_source"] = "real_fixture"
            row["opponent_logo_url"] = (
                badge_by_team_name.get(
                    fixture.opponent
                )
            )
        else:
            row["fixture_source"] = "proxy_last_played"
            row["fixture_difficulty"] = None
            row["opponent_logo_url"] = None

        rows.append(row)

    current_fpl_df = pd.DataFrame(rows)

    # ---------------------------------------------------------------
    # 3. Join model predictions by stable player identity
    # ---------------------------------------------------------------

    if join_col and not predictions.empty:
        pred_copy = predictions.copy()

        # Metadata columns that are strictly driven by
        # current bootstrap-static data.
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

        pred_copy["_norm_join"] = pred_copy[join_col].astype(str).map(_fold_to_ascii_lower)
        if "name_normalized" in pred_copy.columns:
            pred_copy["_norm_alt"] = pred_copy["name_normalized"].astype(str).map(_fold_to_ascii_lower)
        elif "name" in pred_copy.columns:
            pred_copy["_norm_alt"] = pred_copy["name"].astype(str).map(_fold_to_ascii_lower)
        else:
            pred_copy["_norm_alt"] = pred_copy["_norm_join"]

        pred_cols = [
            c
            for c in pred_copy.columns
            if c not in override_cols and c not in ("_norm_join", "_norm_alt")
        ]

        pred_lookup: dict[str, dict[str, Any]] = {}
        for _, p_row in pred_copy.iterrows():
            p_dict = {c: p_row[c] for c in pred_cols}
            k1 = str(p_row.get("_norm_join") or "")
            k2 = str(p_row.get("_norm_alt") or "")
            if k1 and k1 not in pred_lookup:
                pred_lookup[k1] = p_dict
            if k2 and k2 not in pred_lookup:
                pred_lookup[k2] = p_dict

        merged_rows: list[dict[str, Any]] = []

        for _, c_row in current_fpl_df.iterrows():
            c_dict = c_row.to_dict()

            norm_full = c_dict.pop(
                "_norm_full",
                "",
            )

            norm_web = c_dict.pop(
                "_norm_web",
                "",
            )

            is_ambiguous = c_dict.pop(
                "_is_ambiguous",
                False,
            )

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
        current_fpl_df = current_fpl_df.drop(
            columns=[
                "_norm_full",
                "_norm_web",
                "_is_ambiguous",
            ],
            errors="ignore",
        )

        merged = current_fpl_df

    # Ensure predicted_total_points is present if predicted_expected_points is available
    if "predicted_expected_points" in merged.columns and "predicted_total_points" not in merged.columns:
        merged["predicted_total_points"] = merged["predicted_expected_points"]

    # ---------------------------------------------------------------
    # 4. Ensure prediction target columns exist and are None
    #    for unmatched current players
    # ---------------------------------------------------------------

    pred_target_cols = [
        c
        for c in merged.columns
        if c.startswith("predicted_")
        and not c.startswith("predicted_for_gw")
    ]

    for ptc in pred_target_cols:
        merged[ptc] = (
            merged[ptc]
            .astype(object)
            .where(
                merged[ptc].notna(),
                None,
            )
        )

    logger.info(
        "Built current FPL prediction pool: "
        "%d active player(s) from API "
        "(merged on stable player identity).",
        len(merged),
    )

    return merged.reset_index(drop=True)