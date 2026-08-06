"""Unit tests for src.automation.versioning.VersionRegistry."""

from __future__ import annotations

import time
from pathlib import Path

from src.automation.versioning import VersionRegistry


def test_register_creates_a_version_and_copies_the_file(tmp_path: Path) -> None:
    """register() must copy the source file into a new versioned slot."""
    source = tmp_path / "artifact.txt"
    source.write_text("hello")

    registry = VersionRegistry(tmp_path / "versions", max_versions_to_keep=10)
    entry = registry.register(source, {"note": "first"})

    resolved = registry.resolve_path(entry)
    assert resolved.read_text() == "hello"
    assert entry.metadata == {"note": "first"}


def test_register_copies_a_directory_recursively(tmp_path: Path) -> None:
    """register() must copy an entire directory when given one."""
    source_dir = tmp_path / "artifact_dir"
    source_dir.mkdir()
    (source_dir / "a.txt").write_text("a")
    (source_dir / "b.txt").write_text("b")

    registry = VersionRegistry(tmp_path / "versions", max_versions_to_keep=10)
    entry = registry.register(source_dir, {})

    resolved = registry.resolve_path(entry)
    assert (resolved / "a.txt").read_text() == "a"
    assert (resolved / "b.txt").read_text() == "b"


def test_register_raises_for_missing_source(tmp_path: Path) -> None:
    """register() must raise FileNotFoundError for a non-existent source path."""
    registry = VersionRegistry(tmp_path / "versions", max_versions_to_keep=10)
    try:
        registry.register(tmp_path / "does_not_exist.txt", {})
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_list_versions_returns_empty_for_fresh_registry(tmp_path: Path) -> None:
    """A freshly created registry must report zero versions."""
    registry = VersionRegistry(tmp_path / "versions", max_versions_to_keep=10)
    assert registry.list_versions() == []
    assert registry.get_latest() is None


def test_get_latest_returns_most_recently_registered(tmp_path: Path) -> None:
    """get_latest() must return the most recently registered version."""
    source = tmp_path / "artifact.txt"
    registry = VersionRegistry(tmp_path / "versions", max_versions_to_keep=10)

    source.write_text("v1")
    registry.register(source, {})
    time.sleep(0.01)
    source.write_text("v2")
    entry2 = registry.register(source, {})

    latest = registry.get_latest()
    assert latest is not None
    assert latest.version_id == entry2.version_id
    assert registry.resolve_path(latest).read_text() == "v2"


def test_get_by_id_finds_a_specific_version(tmp_path: Path) -> None:
    """get_by_id() must return the matching entry, or None if not found."""
    source = tmp_path / "artifact.txt"
    source.write_text("v1")
    registry = VersionRegistry(tmp_path / "versions", max_versions_to_keep=10)
    entry = registry.register(source, {"tag": "x"})

    found = registry.get_by_id(entry.version_id)
    assert found is not None
    assert found.metadata == {"tag": "x"}
    assert registry.get_by_id("nonexistent") is None


def test_pruning_removes_oldest_versions_beyond_the_limit(tmp_path: Path) -> None:
    """Registering beyond max_versions_to_keep must prune the oldest entries."""
    source = tmp_path / "artifact.txt"
    registry = VersionRegistry(tmp_path / "versions", max_versions_to_keep=2)

    ids = []
    for i in range(4):
        source.write_text(f"v{i}")
        entry = registry.register(source, {})
        ids.append(entry.version_id)
        time.sleep(0.01)

    remaining = registry.list_versions()
    assert len(remaining) == 2
    assert [e.version_id for e in remaining] == ids[-2:]
    # Pruned versions' directories must actually be removed from disk.
    assert not (tmp_path / "versions" / ids[0]).exists()


def test_pruning_disabled_when_max_versions_is_zero(tmp_path: Path) -> None:
    """max_versions_to_keep <= 0 must disable pruning entirely."""
    source = tmp_path / "artifact.txt"
    registry = VersionRegistry(tmp_path / "versions", max_versions_to_keep=0)

    for i in range(5):
        source.write_text(f"v{i}")
        registry.register(source, {})
        time.sleep(0.005)

    assert len(registry.list_versions()) == 5
