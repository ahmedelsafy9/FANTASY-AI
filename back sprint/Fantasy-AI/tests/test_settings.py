"""Unit tests for src.config.settings."""

from __future__ import annotations

from pathlib import Path

from src.config.settings import DataSourceSettings, Paths, Settings, get_settings


def test_get_settings_returns_settings_instance() -> None:
    """get_settings() should return a fully populated Settings object."""
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert isinstance(settings.paths, Paths)
    assert isinstance(settings.data_sources, DataSourceSettings)


def test_paths_are_absolute_and_not_hardcoded() -> None:
    """All resolved paths must be absolute Path objects."""
    paths = Paths()
    for path in (
        paths.data_dir,
        paths.raw_data_dir,
        paths.processed_data_dir,
        paths.external_data_dir,
        paths.models_dir,
        paths.configs_dir,
        paths.logs_dir,
    ):
        assert isinstance(path, Path)
        assert path.is_absolute()


def test_raw_processed_external_are_nested_under_data_dir() -> None:
    """raw/processed/external directories must live under data_dir."""
    paths = Paths()
    assert paths.raw_data_dir.parent == paths.data_dir
    assert paths.processed_data_dir.parent == paths.data_dir
    assert paths.external_data_dir.parent == paths.data_dir


def test_ensure_exists_creates_all_directories(tmp_path: Path, monkeypatch) -> None:
    """ensure_exists() must create every managed directory."""
    monkeypatch.setenv("FANTASY_AI_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FANTASY_AI_MODELS_DIR", str(tmp_path / "models"))
    monkeypatch.setenv("FANTASY_AI_CONFIGS_DIR", str(tmp_path / "configs"))
    monkeypatch.setenv("FANTASY_AI_LOGS_DIR", str(tmp_path / "logs"))

    paths = Paths()
    paths.ensure_exists()

    assert paths.data_dir.exists()
    assert paths.raw_data_dir.exists()
    assert paths.processed_data_dir.exists()
    assert paths.external_data_dir.exists()
    assert paths.models_dir.exists()
    assert paths.configs_dir.exists()
    assert paths.logs_dir.exists()


def test_vaastav_seasons_defaults_to_empty_tuple_when_unset(monkeypatch) -> None:
    """No season should ever be hardcoded: default must be an empty tuple."""
    monkeypatch.delenv("FANTASY_AI_SEASONS", raising=False)
    settings = DataSourceSettings()
    assert settings.vaastav_seasons == ()


def test_vaastav_seasons_parses_env_override(monkeypatch) -> None:
    """FANTASY_AI_SEASONS should be parsed into a tuple of season strings."""
    monkeypatch.setenv("FANTASY_AI_SEASONS", "2022-23,2023-24")
    settings = DataSourceSettings()
    assert settings.vaastav_seasons == ("2022-23", "2023-24")


def test_data_source_urls_have_defaults() -> None:
    """Data source URLs must have sensible, non-empty defaults."""
    settings = DataSourceSettings()
    assert settings.vaastav_repo_url.startswith("https://")
    assert settings.fpl_api_base_url.startswith("https://")
    assert settings.understat_base_url.startswith("https://")


def test_validation_settings_have_sensible_defaults() -> None:
    """ValidationSettings must default to a usable FPL Gameweek range."""
    from src.config.settings import ValidationSettings

    settings = ValidationSettings()
    assert settings.min_gameweek == 1
    assert settings.max_gameweek == 38
    assert "season" in settings.required_columns
