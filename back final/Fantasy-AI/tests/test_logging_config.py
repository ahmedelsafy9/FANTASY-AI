"""Unit tests for src.config.logging_config."""

from __future__ import annotations

import logging
from pathlib import Path

from src.config.logging_config import configure_logging, get_logger
from src.config.settings import Settings


def test_get_logger_returns_named_logger() -> None:
    """get_logger() should return a Logger with the requested name."""
    logger = get_logger("fantasy_ai.test")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "fantasy_ai.test"


def test_configure_logging_is_idempotent_without_force() -> None:
    """Calling configure_logging() repeatedly should not duplicate handlers."""
    configure_logging(force=True)
    handler_count_after_first = len(logging.getLogger().handlers)

    configure_logging()  # no force -> should be a no-op
    handler_count_after_second = len(logging.getLogger().handlers)

    assert handler_count_after_first == handler_count_after_second


def test_configure_logging_respects_configured_level(tmp_path: Path) -> None:
    """The root logger level should match the configured logging level."""
    settings = Settings()
    object.__setattr__(settings.logging, "level", "DEBUG")
    object.__setattr__(settings.logging, "log_to_file", False)

    configure_logging(settings=settings, force=True)

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_creates_log_file_when_enabled(tmp_path: Path, monkeypatch) -> None:
    """When log_to_file is enabled, a log file should be created on disk."""
    monkeypatch.setenv("FANTASY_AI_LOGS_DIR", str(tmp_path))
    settings = Settings()
    object.__setattr__(settings.logging, "log_to_file", True)
    object.__setattr__(settings.logging, "log_filename", "test.log")

    configure_logging(settings=settings, force=True)
    logger = get_logger("fantasy_ai.file_test")
    logger.info("hello world")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert (tmp_path / "test.log").exists()
