"""Model versioning: keeps every trained model artifact, not just the latest.

Wraps :class:`~src.automation.versioning.VersionRegistry` with
model-specific concerns: a model version consists of *two* files (the
``.joblib`` artifact and its JSON metadata) that must travel together,
and "promoting" a version means copying it over the live
``best_model.joblib`` / ``best_model_metadata.json`` the prediction
and API layers read.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from src.automation.versioning import VersionEntry, VersionRegistry
from src.config.logging_config import get_logger

logger = get_logger(__name__)

_MODEL_KEY = "model_filename"
_METADATA_KEY = "metadata_filename"


class ModelVersionManager:
    """Registers, lists, and promotes versioned model artifacts.

    Args:
        versions_dir: Directory model versions are stored under.
        max_versions_to_keep: Oldest versions beyond this count are
            pruned automatically.
    """

    def __init__(self, versions_dir: Path, max_versions_to_keep: int) -> None:
        self._registry = VersionRegistry(versions_dir, max_versions_to_keep)

    def register_model(
        self, model_path: Path, metadata_path: Path, extra_metadata: dict[str, Any]
    ) -> VersionEntry:
        """Version a trained model artifact together with its metadata.

        Args:
            model_path: Path to the ``.joblib`` model file to version.
            metadata_path: Path to the companion JSON metadata file.
            extra_metadata: Additional metadata to record for this
                version (e.g. model name, metrics).

        Returns:
            VersionEntry: The newly registered version.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            staging = Path(tmp_dir) / "model_version"
            staging.mkdir()
            shutil.copy2(model_path, staging / model_path.name)
            shutil.copy2(metadata_path, staging / metadata_path.name)

            metadata = {
                **extra_metadata,
                _MODEL_KEY: model_path.name,
                _METADATA_KEY: metadata_path.name,
            }
            return self._registry.register(staging, metadata)

    def list_versions(self) -> list[VersionEntry]:
        """List every registered model version, oldest first.

        Returns:
            list[VersionEntry]: All registered model versions.
        """
        return self._registry.list_versions()

    def get_latest(self) -> VersionEntry | None:
        """Return the most recently registered model version.

        Returns:
            VersionEntry | None: The latest version, or ``None``.
        """
        return self._registry.get_latest()

    def resolve_model_path(self, entry: VersionEntry) -> Path:
        """Resolve a version entry's model artifact path.

        Args:
            entry: The version entry.

        Returns:
            Path: Absolute path to that version's ``.joblib`` file.
        """
        return self._registry.resolve_path(entry) / entry.metadata[_MODEL_KEY]

    def resolve_metadata_path(self, entry: VersionEntry) -> Path:
        """Resolve a version entry's metadata JSON path.

        Args:
            entry: The version entry.

        Returns:
            Path: Absolute path to that version's metadata file.
        """
        return self._registry.resolve_path(entry) / entry.metadata[_METADATA_KEY]

    def promote_to_best(
        self, entry: VersionEntry, best_model_path: Path, best_metadata_path: Path
    ) -> None:
        """Copy a versioned model over the live "best model" files.

        Args:
            entry: The version to promote.
            best_model_path: Destination for the live model artifact
                (read by the prediction/API layers).
            best_metadata_path: Destination for the live metadata file.
        """
        best_model_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.resolve_model_path(entry), best_model_path)
        shutil.copy2(self.resolve_metadata_path(entry), best_metadata_path)
        logger.info("Promoted model version '%s' to '%s'.", entry.version_id, best_model_path)
