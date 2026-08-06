"""A generic, JSON-backed version registry for artifacts (models or datasets).

Both model versioning and data versioning need the same underlying
mechanics — copy an artifact into a timestamped slot, record it in a
manifest, prune old entries — so that logic lives here once, and
``model_versioning.py`` / ``data_versioning.py`` are thin,
domain-specific wrappers around it.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger

logger = get_logger(__name__)

_REGISTRY_FILENAME = "registry.json"


@dataclass
class VersionEntry:
    """A single recorded version of an artifact.

    Attributes:
        version_id: Unique, sortable identifier (UTC timestamp-based,
            e.g. ``"20240115T093000Z"``).
        created_at: When this version was registered.
        relative_path: Path of the versioned copy, relative to the
            versions directory.
        metadata: Free-form metadata describing this version (e.g.
            model metrics, dataset row counts).
    """

    version_id: str
    created_at: str
    relative_path: str
    metadata: dict[str, Any] = field(default_factory=dict)


class VersionRegistry:
    """Manages a directory of timestamped artifact versions plus a JSON manifest.

    Args:
        versions_dir: Directory versioned copies and the registry file
            live in. Created if it does not already exist.
        max_versions_to_keep: When exceeded, the oldest version(s) are
            pruned (both their files and their registry entry) after a
            new one is registered. ``0`` or a negative value disables
            pruning.
    """

    def __init__(self, versions_dir: Path, max_versions_to_keep: int = 10) -> None:
        self._versions_dir = versions_dir
        self._max_versions_to_keep = max_versions_to_keep
        ensure_directory(self._versions_dir)

    @property
    def _registry_path(self) -> Path:
        return self._versions_dir / _REGISTRY_FILENAME

    def register(self, source_path: Path, metadata: dict[str, Any]) -> VersionEntry:
        """Copy an artifact into a new timestamped slot and record it.

        Args:
            source_path: The file or directory to version. Copied
                as-is (a file stays a file; a directory is copied
                recursively).
            metadata: Free-form metadata to store alongside this
                version (e.g. metrics, row counts).

        Returns:
            VersionEntry: The newly registered version.

        Raises:
            FileNotFoundError: If ``source_path`` does not exist.
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Cannot version a path that does not exist: {source_path}")

        version_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target_dir = self._versions_dir / version_id
        ensure_directory(target_dir)

        if source_path.is_dir():
            shutil.copytree(source_path, target_dir / source_path.name)
            relative_path = f"{version_id}/{source_path.name}"
        else:
            shutil.copy2(source_path, target_dir / source_path.name)
            relative_path = f"{version_id}/{source_path.name}"

        entry = VersionEntry(
            version_id=version_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            relative_path=relative_path,
            metadata=metadata,
        )

        entries = self.list_versions()
        entries.append(entry)
        self._save(entries)
        logger.info("Registered version '%s' (%s).", version_id, relative_path)

        self._prune(entries)
        return entry

    def list_versions(self) -> list[VersionEntry]:
        """List every registered version, oldest first.

        Returns:
            list[VersionEntry]: All registered versions.
        """
        if not self._registry_path.exists():
            return []
        try:
            raw = json.loads(self._registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read version registry at %s: %s", self._registry_path, exc)
            return []
        return [VersionEntry(**item) for item in raw]

    def get_latest(self) -> VersionEntry | None:
        """Return the most recently registered version.

        Returns:
            VersionEntry | None: The latest version, or ``None`` if
            none have been registered.
        """
        entries = self.list_versions()
        return entries[-1] if entries else None

    def get_by_id(self, version_id: str) -> VersionEntry | None:
        """Return a specific version by its identifier.

        Args:
            version_id: The version identifier to look up.

        Returns:
            VersionEntry | None: The matching version, or ``None`` if
            not found.
        """
        return next((e for e in self.list_versions() if e.version_id == version_id), None)

    def resolve_path(self, entry: VersionEntry) -> Path:
        """Resolve a version entry's relative path to an absolute path.

        Args:
            entry: The version entry to resolve.

        Returns:
            Path: The absolute path to this version's artifact.
        """
        return self._versions_dir / entry.relative_path

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save(self, entries: list[VersionEntry]) -> None:
        """Persist the full list of entries to the registry file.

        Args:
            entries: All entries to persist.
        """
        self._registry_path.write_text(
            json.dumps([asdict(e) for e in entries], indent=2), encoding="utf-8"
        )

    def _prune(self, entries: list[VersionEntry]) -> None:
        """Remove the oldest versions beyond ``max_versions_to_keep``.

        Args:
            entries: The current, up-to-date list of entries (oldest
                first), to prune and re-save if needed.
        """
        if self._max_versions_to_keep <= 0 or len(entries) <= self._max_versions_to_keep:
            return

        excess = len(entries) - self._max_versions_to_keep
        to_remove, to_keep = entries[:excess], entries[excess:]

        for entry in to_remove:
            version_dir = self._versions_dir / entry.version_id
            if version_dir.exists():
                shutil.rmtree(version_dir)
            logger.info("Pruned old version '%s'.", entry.version_id)

        self._save(to_keep)
