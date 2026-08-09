"""Runtime dataset loading layer for production and development.

Decouples historical dataset resolution from deployment bundling.
Attempts to load local datasets in development, downloads external
datasets when configured via FANTASY_AI_DATA_URL, or falls back
gracefully to self-contained inference.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pandas as pd
import requests

from src.config.logging_config import get_logger
from src.config.settings import Settings

logger = get_logger(__name__)


def load_external_dataset(settings: Settings) -> pd.DataFrame | None:
    """Load historical dataset from local filesystem or external URL.

    Args:
        settings: Application settings containing path and URL configuration.

    Returns:
        pd.DataFrame | None: The loaded DataFrame, or None if no dataset
        is available.
    """
    local_path = settings.paths.processed_data_dir / "vaastav_features.csv"

    # 1. Local filesystem check (Development mode)
    if settings.environment.lower() != "production" and local_path.exists():
        logger.info("Loading local engineered dataset from %s...", local_path)
        try:
            return pd.read_csv(local_path, low_memory=False)
        except Exception as exc:
            logger.warning("Failed to load local dataset at %s: %s", local_path, exc)

    # 2. External URL check (Production mode or URL override)
    data_url = settings.data_sources.data_url.strip()
    if data_url:
        temp_dir = Path(tempfile.gettempdir())
        cached_file = temp_dir / "fantasy_ai_features_cached.csv"

        if cached_file.exists() and cached_file.stat().st_size > 0:
            logger.info("Loading cached external dataset from %s...", cached_file)
            try:
                return pd.read_csv(cached_file, low_memory=False)
            except Exception as exc:
                logger.warning("Failed to load cached dataset at %s: %s", cached_file, exc)

        logger.info("Downloading external dataset from %s...", data_url)
        try:
            response = requests.get(
                data_url,
                timeout=settings.data_sources.request_timeout_seconds,
            )
            response.raise_for_status()

            cached_file.write_bytes(response.content)
            logger.info("Successfully downloaded and cached external dataset (%d bytes).", len(response.content))
            return pd.read_csv(cached_file, low_memory=False)

        except requests.RequestException as exc:
            logger.error("Failed to download external dataset from %s: %s", data_url, exc)
        except Exception as exc:
            logger.error("Error processing downloaded dataset from %s: %s", data_url, exc)

    # Also check if local_path exists even in production if no data_url specified
    if local_path.exists():
        logger.info("Fallback: loading local dataset at %s...", local_path)
        try:
            return pd.read_csv(local_path, low_memory=False)
        except Exception as exc:
            logger.warning("Failed fallback load of local dataset: %s", exc)

    logger.warning("No external or local dataset available. Proceeding with live self-contained FPL inference.")
    return None
