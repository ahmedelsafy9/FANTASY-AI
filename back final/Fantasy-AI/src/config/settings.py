"""Centralized, environment-aware application settings.

All paths are resolved dynamically relative to the project root instead
of being hardcoded, so the project remains portable across machines and
deployment environments (local, CI, Docker, etc.).

Settings can be overridden via environment variables, which keeps the
configuration flexible without touching source code (12-factor style).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _project_root() -> Path:
    """Resolve the project root directory.

    The root is defined as the parent of the ``src`` package, computed
    dynamically from this file's location so no absolute path is ever
    hardcoded.

    Returns:
        Path: Absolute path to the project root.
    """
    return Path(__file__).resolve().parents[2]


def _env_path(var_name: str, default: Path) -> Path:
    """Resolve a path setting, allowing environment override.

    Args:
        var_name: Name of the environment variable that may override
            the default path.
        default: Default path used when the environment variable is
            not set.

    Returns:
        Path: The resolved, absolute path.
    """
    value = os.environ.get(var_name)
    return Path(value).resolve() if value else default


def _env_str(var_name: str, default: str) -> str:
    """Resolve a string setting, allowing environment override.

    Args:
        var_name: Name of the environment variable.
        default: Default value used when unset.

    Returns:
        str: The resolved value.
    """
    return os.environ.get(var_name, default)


def _env_int(var_name: str, default: int) -> int:
    """Resolve an integer setting, allowing environment override.

    Args:
        var_name: Name of the environment variable.
        default: Default value used when unset or invalid.

    Returns:
        int: The resolved value.
    """
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_bool(var_name: str, default: bool) -> bool:
    """Resolve a boolean setting, allowing environment override.

    Accepts (case-insensitively) "true"/"false", "1"/"0", "yes"/"no".

    Args:
        var_name: Name of the environment variable.
        default: Default value used when unset or unrecognized.

    Returns:
        bool: The resolved value.
    """
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    return raw.strip().lower() in {"true", "1", "yes"}


def _env_tuple(var_name: str, default: str = "") -> tuple[str, ...]:
    """Resolve a comma-separated list setting, allowing environment override.

    Args:
        var_name: Name of the environment variable.
        default: Default comma-separated value used when unset.

    Returns:
        tuple[str, ...]: The resolved, non-empty, whitespace-trimmed values.
    """
    raw = _env_str(var_name, default)
    return tuple(v.strip() for v in raw.split(",") if v.strip())


def _parse_weight_str(weight_str: str) -> dict[str, float]:
    """Parse comma-separated 'metric:weight' string into a dict."""
    if not weight_str or not weight_str.strip():
        return {}
    weights: dict[str, float] = {}
    for item in weight_str.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        parts = item.split(":")
        if len(parts) == 2:
            try:
                weights[parts[0].strip()] = float(parts[1].strip())
            except ValueError:
                continue
    return weights


def _parse_gate_str(gate_str: str) -> dict[str, tuple[str, float]]:
    """Parse comma-separated 'metric:op:val' string into a dict."""
    if not gate_str or not gate_str.strip():
        return {}
    gates: dict[str, tuple[str, float]] = {}
    valid_ops = {"<=", ">=", "<", ">"}
    for item in gate_str.split(","):
        item = item.strip()
        if not item:
            continue
        parts = item.split(":")
        if len(parts) == 3:
            metric = parts[0].strip()
            op = parts[1].strip()
            if op not in valid_ops:
                continue
            try:
                val = float(parts[2].strip())
                gates[metric] = (op, val)
            except ValueError:
                continue
    return gates


@dataclass(frozen=True)
class Paths:
    """Filesystem layout of the project.

    Every attribute is an absolute :class:`~pathlib.Path`, resolved at
    runtime relative to the project root. Nothing here is hardcoded to
    a specific machine.
    """

    root: Path = field(default_factory=_project_root)

    @property
    def data_dir(self) -> Path:
        """Root directory holding all datasets."""
        return _env_path("FANTASY_AI_DATA_DIR", self.root / "data")

    @property
    def raw_data_dir(self) -> Path:
        """Directory holding untouched, as-downloaded data."""
        return self.data_dir / "raw"

    @property
    def processed_data_dir(self) -> Path:
        """Directory holding cleaned / feature-engineered data."""
        return self.data_dir / "processed"

    @property
    def external_data_dir(self) -> Path:
        """Directory holding third-party reference data."""
        return self.data_dir / "external"

    @property
    def models_dir(self) -> Path:
        """Directory holding trained model artifacts."""
        return _env_path("FANTASY_AI_MODELS_DIR", self.root / "models")

    @property
    def configs_dir(self) -> Path:
        """Directory holding configuration files (YAML/JSON/etc.)."""
        return _env_path("FANTASY_AI_CONFIGS_DIR", self.root / "configs")

    @property
    def logs_dir(self) -> Path:
        """Directory holding log files."""
        return _env_path("FANTASY_AI_LOGS_DIR", self.root / "logs")

    def ensure_exists(self) -> None:
        """Create every managed directory if it does not already exist."""
        for directory in (
            self.data_dir,
            self.raw_data_dir,
            self.processed_data_dir,
            self.external_data_dir,
            self.models_dir,
            self.configs_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class DataSourceSettings:
    """Settings related to external data sources.

    Note that no season is hardcoded: ``vaastav_seasons`` defaults to an
    empty tuple, signalling "auto-detect all available seasons" to the
    ``VaastavDataSource`` implementation. A caller may still pin specific
    seasons via the ``FANTASY_AI_SEASONS`` environment variable.
    """

    vaastav_repo_url: str = field(
        default_factory=lambda: _env_str(
            "FANTASY_AI_VAASTAV_REPO_URL",
            "https://github.com/vaastav/Fantasy-Premier-League",
        )
    )
    fpl_api_base_url: str = field(
        default_factory=lambda: _env_str(
            "FANTASY_AI_FPL_API_BASE_URL",
            "https://fantasy.premierleague.com/api",
        )
    )
    understat_base_url: str = field(
        default_factory=lambda: _env_str(
            "FANTASY_AI_UNDERSTAT_BASE_URL",
            "https://understat.com",
        )
    )
    vaastav_seasons: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            s for s in _env_str("FANTASY_AI_SEASONS", "").split(",") if s
        )
    )
    request_timeout_seconds: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_REQUEST_TIMEOUT", 30)
    )
    request_max_retries: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_REQUEST_MAX_RETRIES", 3)
    )


@dataclass(frozen=True)
class LoggingSettings:
    """Settings controlling application-wide logging behavior."""

    level: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_LOG_LEVEL", "INFO")
    )
    log_to_file: bool = field(
        default_factory=lambda: _env_str("FANTASY_AI_LOG_TO_FILE", "true").lower()
        == "true"
    )
    log_filename: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_LOG_FILENAME", "fantasy_ai.log")
    )


@dataclass(frozen=True)
class ValidationSettings:
    """Settings controlling dataset validation thresholds and rules.

    Nothing here is hardcoded inside individual checks — every rule a
    check applies is configurable through this settings group (and,
    transitively, through environment variables).
    """

    required_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_REQUIRED_COLUMNS", "season,name,total_points"
            ).split(",")
            if c
        )
    )
    gameweek_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_GAMEWEEK_COLUMNS", "GW,round").split(",")
            if c
        )
    )
    min_gameweek: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_MIN_GAMEWEEK", 1)
    )
    max_gameweek: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_MAX_GAMEWEEK", 38)
    )
    player_id_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_PLAYER_ID_COLUMNS", "element,name").split(",")
            if c
        )
    )
    duplicate_key_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_DUPLICATE_KEY_COLUMNS", "season,name,GW"
            ).split(",")
            if c
        )
    )
    expected_numeric_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_NUMERIC_COLUMNS",
                "total_points,minutes,goals_scored,assists,bonus,bps,"
                "clean_sheets,goals_conceded,own_goals,penalties_missed,"
                "penalties_saved,red_cards,yellow_cards,saves,value",
            ).split(",")
            if c
        )
    )
    max_issues_in_report: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_MAX_ISSUES_IN_REPORT", 50)
    )


@dataclass(frozen=True)
class PreprocessingSettings:
    """Settings controlling dataset cleaning and normalization rules.

    As with :class:`ValidationSettings`, every column list and rule
    used by a preprocessing step is configurable here rather than
    hardcoded inside the step itself.
    """

    name_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c for c in _env_str("FANTASY_AI_NAME_COLUMNS", "name").split(",") if c
        )
    )
    boolean_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_BOOLEAN_COLUMNS", "was_home").split(",")
            if c
        )
    )
    datetime_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_DATETIME_COLUMNS", "kickoff_time").split(",")
            if c
        )
    )
    integer_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_INTEGER_COLUMNS",
                "GW,round,element,total_points,minutes,goals_scored,assists,"
                "clean_sheets,goals_conceded,own_goals,penalties_saved,"
                "penalties_missed,yellow_cards,red_cards,saves,bonus,bps,"
                "selected,transfers_in,transfers_out,transfers_balance,value",
            ).split(",")
            if c
        )
    )
    float_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_FLOAT_COLUMNS", "ict_index,influence,creativity,threat,xP"
            ).split(",")
            if c
        )
    )
    zero_fill_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_ZERO_FILL_COLUMNS",
                "goals_scored,assists,clean_sheets,goals_conceded,own_goals,"
                "penalties_saved,penalties_missed,yellow_cards,red_cards,saves,"
                "bonus,bps,minutes,total_points",
            ).split(",")
            if c
        )
    )


@dataclass(frozen=True)
class FeatureEngineeringSettings:
    """Settings controlling the feature engineering pipeline.

    As with the other settings groups, every column list, window
    size, and weight used by a feature step is configurable here
    rather than hardcoded inside the step itself.
    """

    player_id_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_FEATURE_PLAYER_ID_COLUMNS", "element,name_normalized,name"
            ).split(",")
            if c
        )
    )
    chronological_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_CHRONOLOGICAL_COLUMNS", "season,GW").split(",")
            if c
        )
    )
    rolling_windows: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(w)
            for w in _env_str("FANTASY_AI_ROLLING_WINDOWS", "3,5,10").split(",")
            if w
        )
    )
    points_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_POINTS_COLUMNS", "total_points").split(",")
            if c
        )
    )
    minutes_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c for c in _env_str("FANTASY_AI_MINUTES_COLUMNS", "minutes").split(",") if c
        )
    )
    bps_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c for c in _env_str("FANTASY_AI_BPS_COLUMNS", "bps").split(",") if c
        )
    )
    ict_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c for c in _env_str("FANTASY_AI_ICT_COLUMNS", "ict_index").split(",") if c
        )
    )
    xg_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_XG_COLUMNS", "expected_goals,xG").split(",")
            if c
        )
    )
    xa_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_XA_COLUMNS", "expected_assists,xA").split(",")
            if c
        )
    )
    home_column: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_HOME_COLUMN", "was_home")
    )
    kickoff_time_column: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_KICKOFF_TIME_COLUMN", "kickoff_time")
    )
    default_rest_days: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_DEFAULT_REST_DAYS", 7)
    )
    team_column: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_TEAM_COLUMN", "team")
    )
    opponent_column: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_OPPONENT_COLUMN", "opponent_team")
    )
    strength_source_column: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_STRENGTH_SOURCE_COLUMN", "total_points")
    )
    value_column: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_VALUE_COLUMN", "value")
    )
    price_trend_windows: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(w)
            for w in _env_str("FANTASY_AI_PRICE_TREND_WINDOWS", "1,5").split(",")
            if w
        )
    )
    form_index_windows: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(w)
            for w in _env_str("FANTASY_AI_FORM_INDEX_WINDOWS", "3,5,10").split(",")
            if w
        )
    )
    form_index_weights: tuple[float, ...] = field(
        default_factory=lambda: tuple(
            float(w)
            for w in _env_str("FANTASY_AI_FORM_INDEX_WEIGHTS", "0.5,0.3,0.2").split(",")
            if w
        )
    )


@dataclass(frozen=True)
class TrainingSettings:
    """Settings controlling the model training and evaluation pipeline."""

    target_column: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_TARGET_COLUMN", "total_points")
    )
    excluded_feature_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_EXCLUDED_FEATURE_COLUMNS",
                # Identifier / free-text columns, excluded regardless of timing:
                "season,name,team,opponent_team,kickoff_time,element,fixture,round,"
                # Same-Gameweek MATCH-OUTCOME stats: these are only known AFTER a
                # match is played, so using them (unlagged) to predict that same
                # match's total_points is data leakage — total_points is itself a
                # near-deterministic function of several of these under FPL's
                # scoring rules (e.g. minutes + goals + assists + bonus). The
                # rolling/lagged versions of these (e.g. "minutes_avg_last_3")
                # produced by feature engineering remain valid pre-match features
                # and are NOT excluded here.
                "minutes,goals_scored,assists,clean_sheets,goals_conceded,own_goals,"
                "penalties_missed,penalties_saved,red_cards,yellow_cards,saves,"
                "bonus,bps,influence,creativity,threat,ict_index,"
                "expected_goals,expected_assists,expected_goal_involvements,"
                "expected_goals_conceded,in_dreamteam,starts,selected,"
                "transfers_in,transfers_out,transfers_balance",
            ).split(",")
            if c
        )
    )
    chronological_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str("FANTASY_AI_TRAINING_CHRONOLOGICAL_COLUMNS", "season,GW").split(
                ","
            )
            if c
        )
    )
    test_fraction: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_TEST_FRACTION", "0.2"))
    )
    random_state: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_RANDOM_STATE", 42)
    )
    primary_metric: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_PRIMARY_METRIC", "mae")
    )
    random_forest_n_estimators: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_RF_N_ESTIMATORS", 300)
    )
    random_forest_max_depth: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_RF_MAX_DEPTH", 12)
    )
    boosted_n_estimators: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_BOOSTED_N_ESTIMATORS", 300)
    )
    boosted_max_depth: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_BOOSTED_MAX_DEPTH", 6)
    )
    boosted_learning_rate: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_BOOSTED_LEARNING_RATE", "0.05"))
    )
    season_weight_min: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_SEASON_WEIGHT_MIN", "1.0"))
    )
    season_weight_max: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_SEASON_WEIGHT_MAX", "3.0"))
    )
    season_weight_strategy: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_SEASON_WEIGHT_STRATEGY", "linear")
    )
    promotion_strategy: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_PROMOTION_STRATEGY", "composite")
    )
    promotion_metric_weights: dict[str, float] = field(
        default_factory=lambda: _parse_weight_str(
            _env_str(
                "FANTASY_AI_PROMOTION_METRIC_WEIGHTS",
                "rmse:0.25,mae:0.15,spearman_rho:0.20,recall_6:0.20,recall_10:0.10,precision_6:0.10",
            )
        )
    )
    promotion_gates: dict[str, tuple[str, float]] = field(
        default_factory=lambda: _parse_gate_str(
            _env_str("FANTASY_AI_PROMOTION_GATES", "rmse:<=:3.0,recall_6:>=:0.05")
        )
    )
    dl_hidden_layers: tuple[int, ...] = field(
        default_factory=lambda: tuple(
            int(x)
            for x in _env_str("FANTASY_AI_DL_HIDDEN_LAYERS", "256,128,64").split(",")
            if x
        )
    )
    dl_dropout: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_DL_DROPOUT", "0.2"))
    )
    dl_learning_rate: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_DL_LEARNING_RATE", "0.001"))
    )
    dl_weight_decay: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_DL_WEIGHT_DECAY", "0.0001"))
    )
    dl_batch_size: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_DL_BATCH_SIZE", 512)
    )
    dl_epochs: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_DL_EPOCHS", 200)
    )
    dl_patience: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_DL_PATIENCE", 15)
    )
    dl_use_batch_norm: bool = field(
        default_factory=lambda: _env_bool("FANTASY_AI_DL_USE_BATCH_NORM", True)
    )
    dl_loss_beta: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_DL_LOSS_BETA", "4.0"))
    )
    dl_high_score_weight_power: float = field(
        default_factory=lambda: float(_env_str("FANTASY_AI_DL_HIGH_SCORE_WEIGHT_POWER", "0.0"))
    )
    dl_use_discrete_sample_weights: bool = field(
        default_factory=lambda: _env_bool("FANTASY_AI_DL_USE_DISCRETE_SAMPLE_WEIGHTS", True)
    )


@dataclass(frozen=True)
class PredictionSettings:
    """Settings controlling the prediction pipeline."""

    export_id_columns: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_EXPORT_ID_COLUMNS", "element,name,team,value"
            ).split(",")
            if c
        )
    )
    max_valid_gameweek: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_MAX_GAMEWEEK_PREDICTION", 38)
    )


@dataclass(frozen=True)
class ApiSettings:
    """Settings controlling the FastAPI application."""

    title: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_API_TITLE", "Fantasy-AI API")
    )
    version: str = field(default_factory=lambda: _env_str("FANTASY_AI_API_VERSION", "0.1.0"))
    docs_url: str = field(default_factory=lambda: _env_str("FANTASY_AI_API_DOCS_URL", "/swagger"))
    top_players_default_limit: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_TOP_PLAYERS_DEFAULT_LIMIT", 10)
    )
    top_players_max_limit: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_TOP_PLAYERS_MAX_LIMIT", 100)
    )
    captain_min_minutes_avg: float = field(
        default_factory=lambda: float(
            _env_str("FANTASY_AI_CAPTAIN_MIN_MINUTES_AVG", "60.0")
        )
    )
    # ------------------------------------------------------------------
    # CORS. Localhost dev origins are always allowed (harmless — they only
    # let a developer's own machine call the API). Production frontend
    # origin(s) must be supplied explicitly via FANTASY_AI_CORS_ORIGINS
    # (comma-separated, e.g. "https://myapp.vercel.app,https://myapp.com");
    # nothing wildcard-y is ever allowed automatically.
    # ------------------------------------------------------------------
    cors_allowed_origins: tuple[str, ...] = field(
        default_factory=lambda: _env_tuple("FANTASY_AI_CORS_ORIGINS")
    )
    cors_allow_credentials: bool = field(
        default_factory=lambda: _env_bool("FANTASY_AI_CORS_ALLOW_CREDENTIALS", False)
    )
    # ------------------------------------------------------------------
    # Rate limiting. Every route (including "/") shares this default
    # unless overridden per-route. "memory://" only rate-limits within a
    # single running process/instance — fine for a single Fly.io machine,
    # NOT sufficient once there is more than one instance/worker or on
    # a per-invocation serverless platform. Point
    # FANTASY_AI_RATE_LIMIT_STORAGE_URI at a shared store (e.g.
    # "redis://<host>:6379") for multi-instance deployments.
    # ------------------------------------------------------------------
    rate_limit_default: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_RATE_LIMIT_DEFAULT", "60/minute")
    )
    rate_limit_storage_uri: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_RATE_LIMIT_STORAGE_URI", "memory://")
    )


@dataclass(frozen=True)
class AutomationSettings:
    """Settings controlling the automated update/retrain pipeline (Sprint 9)."""

    current_season: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_CURRENT_SEASON", "")
    )
    retrain_min_improvement: float = field(
        default_factory=lambda: float(
            _env_str("FANTASY_AI_RETRAIN_MIN_IMPROVEMENT", "0.0")
        )
    )
    dry_run: bool = field(
        default_factory=lambda: _env_bool("FANTASY_AI_DRY_RUN", False)
    )
    max_versions_to_keep: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_MAX_VERSIONS_TO_KEEP", 10)
    )
    fpl_api_events_path: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_FPL_EVENTS_PATH", "bootstrap-static/")
    )
    fpl_api_live_event_path_template: str = field(
        default_factory=lambda: _env_str(
            "FANTASY_AI_FPL_LIVE_EVENT_PATH_TEMPLATE", "event/{event_id}/live/"
        )
    )
    fpl_api_fixtures_path: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_FPL_FIXTURES_PATH", "fixtures/")
    )


@dataclass(frozen=True)
class FixtureAwareSettings:
    """Settings controlling fixture-aware feature engineering and next-GW prediction.

    Kept as its own settings group (rather than folded into
    ``FeatureEngineeringSettings``) since it spans three concerns:
    historical opponent-ID normalization (preprocessing), a new
    leakage-safe training feature (feature engineering), and the
    fixture-aware next-Gameweek builder (prediction) — all driven by
    the same underlying team/fixture reference data.
    """

    team_id_column_candidates: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            c
            for c in _env_str(
                "FANTASY_AI_TEAM_ID_COLUMNS", "team_id,team_a,team_h"
            ).split(",")
            if c
        )
    )
    team_mapping_cache_path: str = field(
        default_factory=lambda: _env_str(
            "FANTASY_AI_TEAM_MAPPING_CACHE", "team_mapping.json"
        )
    )
    form_trend_short_window: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_FORM_TREND_SHORT_WINDOW", 3)
    )
    form_trend_long_window: int = field(
        default_factory=lambda: _env_int("FANTASY_AI_FORM_TREND_LONG_WINDOW", 10)
    )


@dataclass(frozen=True)
class Settings:
    """Top-level application settings, aggregating all setting groups."""

    environment: str = field(
        default_factory=lambda: _env_str("FANTASY_AI_ENV", "development")
    )
    paths: Paths = field(default_factory=Paths)
    data_sources: DataSourceSettings = field(default_factory=DataSourceSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    validation: ValidationSettings = field(default_factory=ValidationSettings)
    preprocessing: PreprocessingSettings = field(default_factory=PreprocessingSettings)
    feature_engineering: FeatureEngineeringSettings = field(
        default_factory=FeatureEngineeringSettings
    )
    training: TrainingSettings = field(default_factory=TrainingSettings)
    prediction: PredictionSettings = field(default_factory=PredictionSettings)
    api: ApiSettings = field(default_factory=ApiSettings)
    automation: AutomationSettings = field(default_factory=AutomationSettings)
    fixture_aware: FixtureAwareSettings = field(default_factory=FixtureAwareSettings)


def get_settings() -> Settings:
    """Build and return a fresh :class:`Settings` instance.

    A factory function (rather than a module-level singleton) is used
    so tests can freely override environment variables and obtain a
    clean settings object without dealing with stale cached state.

    Returns:
        Settings: A fully populated settings object.
    """
    return Settings()
