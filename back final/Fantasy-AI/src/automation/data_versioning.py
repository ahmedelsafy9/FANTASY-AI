"""Data versioning: snapshots a dataset file each time the pipeline runs.

Wraps :class:`~src.automation.versioning.VersionRegistry` with a
dataset-specific concern: cheaply detecting whether a dataset actually
changed since the last snapshot (via a content hash), so the
automation pipeline can skip retraining when nothing new arrived.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from src.automation.versioning import VersionEntry, VersionRegistry
from src.config.logging_config import get_logger

logger = get_logger(__name__)

_HASH_KEY = "content_hash"
_CHUNK_SIZE = 1024 * 1024


class DataVersionManager:
    """Registers and inspects versioned dataset snapshots.

    Args:
        versions_dir: Directory dataset versions are stored under.
        max_versions_to_keep: Oldest versions beyond this count are
            pruned automatically.
    """

    def __init__(self, versions_dir: Path, max_versions_to_keep: int) -> None:
        self._registry = VersionRegistry(versions_dir, max_versions_to_keep)

    def snapshot(self, dataset_path: Path, extra_metadata: dict[str, Any]) -> VersionEntry:
        """Version a dataset file, recording its content hash.

        Args:
            dataset_path: Path to the dataset file to snapshot.
            extra_metadata: Additional metadata to record (e.g. row
                count, column count).

        Returns:
            VersionEntry: The newly registered version.
        """
        content_hash = _hash_file(dataset_path)
        metadata = {**extra_metadata, _HASH_KEY: content_hash}
        return self._registry.register(dataset_path, metadata)

    def has_changed_since_last_snapshot(self, dataset_path: Path) -> bool:
        """Check whether a dataset differs from the most recent snapshot.

        Args:
            dataset_path: Path to the current dataset file.

        Returns:
            bool: ``True`` if there is no previous snapshot, or if the
            current file's content hash differs from it.
        """
        latest = self._registry.get_latest()
        if latest is None:
            return True
        current_hash = _hash_file(dataset_path)
        return current_hash != latest.metadata.get(_HASH_KEY)

    def list_versions(self) -> list[VersionEntry]:
        """List every registered dataset version, oldest first.

        Returns:
            list[VersionEntry]: All registered dataset versions.
        """
        return self._registry.list_versions()

    def get_latest(self) -> VersionEntry | None:
        """Return the most recently registered dataset version.

        Returns:
            VersionEntry | None: The latest version, or ``None``.
        """
        return self._registry.get_latest()


def _hash_file(path: Path) -> str:
    """Compute a SHA-256 hash of a file's contents.

    Args:
        path: The file to hash.

    Returns:
        str: The hex-encoded SHA-256 digest.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()
