"""Champion/challenger selection records for trained models."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.common.file_utils import ensure_directory


@dataclass
class ModelSelectionRecord:
    """Auditable record of why a model was chosen."""

    task: str
    candidate: str
    selected: bool
    rationale: str
    train_period: str
    validation_period: str
    dataset_version: str
    feature_schema_version: str
    metrics: dict[str, float]
    artifact_path: str
    artifact_sha256: str | None
    trained_at: str
    software_versions: dict[str, str] = field(default_factory=dict)
    ensemble: bool = False


def file_sha256(path: Path) -> str | None:
    """Return a content checksum, or None if the file is missing."""
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_selection_record(path: Path, record: ModelSelectionRecord) -> Path:
    """Persist a selection record as JSON."""
    ensure_directory(path.parent)
    payload: dict[str, Any] = asdict(record)
    payload["written_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path
