"""Builds the API's application state once at startup.

Loading the trained model, fetching live FPL metadata, and computing
next-Gameweek predictions are done at process startup / warm initialization.

In production (Vercel Serverless), historical datasets are loaded via
external URL if configured, or the system safely falls back to live
self-contained FPL API predictions.
"""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import requests

from src.config.logging_config import get_logger
from src.config.settings import Settings
from src.core.exceptions import FantasyAIError
from src.data_collection.services.team_mapping_service import TeamMappingService
from src.data_collection.sources.fpl_api_source import FPLApiDataSource
from src.data_runtime.external_data import load_external_dataset
from src.metadata.player_metadata import PlayerMetadata, build_player_metadata
from src.metadata.team_metadata import TeamMetadata, build_team_metadata
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
    engineered_data: pd.DataFrame | None
    loaded_model: LoadedModel
    predictions: pd.DataFrame
    player_id_column: str
    live_metadata_available: bool = False


def build_app_state(settings: Settings) -> AppState:
    """Load model, optional historical data, live FPL metadata and compute predictions."""

    # 1. Load trained model artifact and metadata
    model_path = settings.paths.models_dir / "best_model.joblib"
    metadata_path = settings.paths.models_dir / "best_model_metadata.json"
    loaded_model = load_model(model_path, metadata_path)

    # 2. Try loading historical engineered dataset via runtime loader
    engineered_data = load_external_dataset(settings)

    player_id_column = "element"
    if engineered_data is not None and not engineered_data.empty:
        candidate = next(
            (c for c in settings.feature_engineering.player_id_columns if c in engineered_data.columns),
            None,
        )
        if candidate:
            player_id_column = candidate

    # 3. Best-effort fetch of live FPL metadata & fixtures
    (
        team_fixtures,
        team_metadata,
        player_metadata,
        upcoming_team_fixtures,
    ) = _try_fetch_live_metadata(settings)

    live_metadata_available = bool(team_fixtures or team_metadata or player_metadata)

    # 4. Generate predictions
    prediction_service = PredictionService(loaded_model)

    if engineered_data is not None and not engineered_data.empty:
        next_gw_rows = build_fixture_aware_next_gameweek_rows(
            engineered_data,
            player_id_columns=settings.feature_engineering.player_id_columns,
            chronological_columns=settings.feature_engineering.chronological_columns,
            max_valid_gameweek=settings.prediction.max_valid_gameweek,
            team_fixtures=team_fixtures,
        )
        raw_predictions = prediction_service.predict(next_gw_rows)
    else:
        # Self-contained mode for Vercel deployment without historical CSV
        raw_predictions = _build_self_contained_predictions(
            loaded_model=loaded_model,
            prediction_service=prediction_service,
            player_metadata=player_metadata,
            team_metadata=team_metadata,
            team_fixtures=team_fixtures,
            player_id_column=player_id_column,
        )

    # 5. Build current FPL prediction pool using bootstrap-static as authority
    predictions = _build_current_fpl_prediction_pool(
        predictions=raw_predictions,
        player_id_column=player_id_column,
        team_fixtures=team_fixtures,
        team_metadata=team_metadata,
        player_metadata=player_metadata,
        upcoming_team_fixtures=upcoming_team_fixtures,
    )

    logger.info(
        "API state ready: %d current-season player(s), model '%s', live metadata available=%s.",
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


def _build_self_contained_predictions(
    loaded_model: LoadedModel,
    prediction_service: PredictionService,
    player_metadata: dict[int, PlayerMetadata] | None,
    team_metadata: dict[int, TeamMetadata] | None,
    team_fixtures: dict[str, ResolvedFixture] | None,
    player_id_column: str,
) -> pd.DataFrame:
    """Construct prediction rows for active current players using live metadata and model medians."""
    if not player_metadata:
        logger.warning("No player metadata available for self-contained inference.")
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for pid, meta in player_metadata.items():
        full_name = f"{meta.first_name or ''} {meta.second_name or ''}".strip()
        norm_full = str(_fold_to_ascii_lower(full_name)) if full_name else ""
        norm_web = str(_fold_to_ascii_lower(meta.web_name)) if meta.web_name else ""

        team_name = (
            team_metadata[meta.team_id].name
            if meta.team_id is not None and team_metadata and meta.team_id in team_metadata
            else "Unknown"
        )
        fixture = team_fixtures.get(team_name) if team_fixtures else None

        row: dict[str, Any] = {
            player_id_column: pid,
            "id": pid,
            "element": pid,
            "name": meta.web_name,
            "name_normalized": norm_full or norm_web,
            "value": meta.value or meta.now_cost or 50,
            "GW": fixture.gameweek if fixture else 1,
            "was_home": int(fixture.is_home) if fixture else 1,
            "is_home": int(fixture.is_home) if fixture else 1,
            "team": team_name,
            "opponent_team": fixture.opponent if fixture else "Unknown",
        }
        rows.append(row)

    df_rows = pd.DataFrame(rows)
    for col in loaded_model.feature_columns:
        if col not in df_rows.columns:
            df_rows[col] = None

    return prediction_service.predict(df_rows)



def _try_fetch_live_metadata(
    settings: Settings,
) -> tuple[
    dict[str, ResolvedFixture] | None,
    dict[int, TeamMetadata] | None,
    dict[int, PlayerMetadata] | None,
    dict[str, list[UpcomingFixture]] | None,
]:
    """Best-effort fetch of live fixtures + current FPL metadata."""
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
        bootstrap_path = live_dir / "bootstrap_static.json"

        try:
            live_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            live_dir = Path(tempfile.gettempdir()) / "fpl_api"
            live_dir.mkdir(parents=True, exist_ok=True)
            bootstrap_path = live_dir / "bootstrap_static.json"

        if not bootstrap_path.exists():
            try:
                fpl_source.download(live_dir)
            except Exception as exc:
                logger.warning("FPL download failed (%s); fetching bootstrap directly...", exc)
                resp = requests.get(
                    f"{settings.data_sources.fpl_api_base_url}/bootstrap-static/",
                    timeout=settings.data_sources.request_timeout_seconds,
                )
                resp.raise_for_status()
                bootstrap_path.write_text(resp.text, encoding="utf-8")

        bootstrap = json.loads(bootstrap_path.read_text(encoding="utf-8"))
        teams_raw = bootstrap.get("teams", [])

        mapping_cache_path = (
            settings.paths.external_data_dir / settings.fixture_aware.team_mapping_cache_path
        )
        mapping_service = TeamMappingService(mapping_cache_path)
        team_id_to_name = mapping_service.build_mapping(teams_raw)

        fixtures_raw = fpl_source.get_fixtures(future_only=True)

        team_fixtures = resolve_team_fixtures(
            fixtures_raw,
            team_id_to_name,
        )

        team_metadata = build_team_metadata(teams_raw)

        upcoming_team_fixtures = resolve_team_upcoming_fixtures(
            fixtures_raw,
            team_id_to_name,
            team_metadata=team_metadata,
            max_fixtures=5,
        )

        player_metadata = build_player_metadata(bootstrap.get("elements", []))

        return (
            team_fixtures,
            team_metadata,
            player_metadata,
            upcoming_team_fixtures,
        )

    except (FantasyAIError, OSError, ValueError, requests.RequestException) as exc:
        logger.warning(
            "Live fixture/metadata enrichment unavailable at startup (%s); fallback mode enabled.",
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
    """Legacy helper function for backward compatibility with existing unit tests."""
    df = _build_current_fpl_prediction_pool(
        predictions=model_predictions,
        player_id_column=player_id_column,
        team_fixtures=None,
        team_metadata=team_metadata,
        player_metadata=player_metadata,
    )
    if "predicted_total_points" in df.columns:
        df["predicted_total_points"] = df["predicted_total_points"].fillna(0.0)
    if "fixture_source" in df.columns:
        df["fixture_source"] = df["fixture_source"].fillna("no_historical_data")
    return df



def _build_current_fpl_prediction_pool(

    predictions: pd.DataFrame,
    player_id_column: str,
    team_fixtures: dict[str, ResolvedFixture] | None,
    team_metadata: dict[int, TeamMetadata] | None,
    player_metadata: dict[int, PlayerMetadata] | None,
    upcoming_team_fixtures: dict[str, list[UpcomingFixture]] | None = None,
) -> pd.DataFrame:
    """Build the active prediction pool using bootstrap-static as the authority."""
    if not player_metadata or not team_metadata:
        logger.warning("Live FPL metadata unavailable; using historical predictions as fallback.")
        fallback_df = predictions.copy() if not predictions.empty else pd.DataFrame()
        for col in ("photo_url", "team_logo_url", "opponent_logo_url"):
            if col not in fallback_df.columns:
                fallback_df[col] = None
        if "upcoming_fixtures" not in fallback_df.columns:
            fallback_df["upcoming_fixtures"] = [[] for _ in range(len(fallback_df))]
        return fallback_df

    join_col = next(
        (c for c in ("name_normalized", "name") if c in predictions.columns),
        None,
    )

    rows = []
    badge_by_team_name = {
        metadata.name: metadata.badge_url for metadata in team_metadata.values()
    }

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

    if join_col and not predictions.empty:
        pred_copy = predictions.copy()
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
            "element",
            "id",
        }
        pred_cols = [c for c in pred_copy.columns if c == join_col or c not in override_cols]
        pred_subset = pred_copy[pred_cols].drop_duplicates(subset=[join_col])

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
                for k, v in matched_pred.items():
                    if k not in c_dict or c_dict.get(k) is None:
                        c_dict[k] = v
                    elif k in ("opponent_team", "predicted_for_gw", "is_home", "fixture_difficulty", "fixture_source") and c_dict.get("fixture_source") != "real_fixture":
                        c_dict[k] = v
            else:
                if c_dict.get("fixture_source") != "real_fixture":
                    c_dict["fixture_source"] = "no_historical_data"

            merged_rows.append(c_dict)



        merged = pd.DataFrame(merged_rows)
    else:
        current_fpl_df = current_fpl_df.drop(
            columns=["_norm_full", "_norm_web", "_is_ambiguous"], errors="ignore"
        )
        merged = current_fpl_df

    pred_target_cols = [
        c for c in merged.columns if c.startswith("predicted_") and not c.startswith("predicted_for_gw")
    ]
    for ptc in pred_target_cols:
        merged[ptc] = merged[ptc].astype(object).where(merged[ptc].notna(), None)

    logger.info(
        "Built current FPL prediction pool: %d active player(s) from API.",
        len(merged),
    )
    return merged.reset_index(drop=True)