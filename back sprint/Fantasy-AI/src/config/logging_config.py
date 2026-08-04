"""Centralized logging configuration for Fantasy-AI.

Every entry point of the application (scripts, services, the API, tests)
should call :func:`configure_logging` once at startup, then obtain
module-level loggers via ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from src.config.settings import Settings, get_settings

_CONFIGURED = False

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(settings: Settings | None = None, *, force: bool = False) -> None:
    """Configure the root logger for the whole application.

    This function is idempotent: calling it multiple times will not
    duplicate handlers, unless ``force=True`` is passed (useful in
    tests that need to reconfigure logging under different settings).

    Args:
        settings: Application settings to derive logging configuration
            from. When ``None``, settings are loaded via
            :func:`~src.config.settings.get_settings`.
        force: When ``True``, existing handlers are removed and logging
            is reconfigured from scratch.

    Returns:
        None
    """
    global _CONFIGURED

    if _CONFIGURED and not force:
        return

    resolved_settings = settings or get_settings()
    log_settings = resolved_settings.logging
    paths = resolved_settings.paths

    root_logger = logging.getLogger()
    root_logger.setLevel(log_settings.level.upper())

    if force:
        for handler in list(root_logger.handlers):
            root_logger.removeHandler(handler)

    formatter = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    if log_settings.log_to_file:
        paths.logs_dir.mkdir(parents=True, exist_ok=True)
        log_file_path: Path = paths.logs_dir / log_settings.log_filename
        file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module-level logger, configuring logging if needed.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        logging.Logger: A configured logger instance.
    """
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)
