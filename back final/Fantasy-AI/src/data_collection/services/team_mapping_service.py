"""Resolves the numeric-team-ID vs team-name domain mismatch.

**Root cause investigation** (Phase 1): the Vaastav historical dataset's
``team`` column holds a team's real name (e.g. ``"Liverpool"``) in every
season, but ``opponent_team`` is inconsistent across seasons — some
seasons store the opponent's real name, others store a small integer
(FPL's internal team ID for that season, 1-20). ``TeamStrengthStep``'s
existing domain-compatibility check (Sprint 5) correctly detects this
and skips ``opponent_strength`` rather than silently joining on
incompatible values — but skipping isn't a fix, just safe behavior.

**The fix**: build a team-ID -> team-name mapping from the FPL API's
``bootstrap-static`` teams list (the authoritative source for "which ID
is which team", refreshed each season) and use it to normalize a
numeric ``opponent_team`` column to team names *before* feature
engineering runs — so ``TeamStrengthStep``'s join then succeeds against
two name-domain columns, instead of being skipped.

**Known limitation**: FPL team IDs are NOT stable across seasons (e.g.
promoted/relegated clubs cause ID reuse). A single current-season
mapping cannot correctly resolve historical seasons' numeric IDs if the
same ID mapped to a different team in a different season. Where the
raw data doesn't distinguish which season a numeric ID belongs to, this
is applied per-season using the mapping snapshot fetched at the time of
processing — correct for the current/most recent season's opponent IDs
(the common case for newer Vaastav data), but historical seasons whose
``opponent_team`` uses since-reassigned IDs may still resolve
incorrectly. This is documented rather than silently assumed correct;
see :meth:`TeamMappingService.build_mapping` for how to verify.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.common.file_utils import ensure_directory
from src.config.logging_config import get_logger

logger = get_logger(__name__)


class TeamMappingService:
    """Builds and caches a numeric-team-ID -> team-name mapping."""

    def __init__(self, cache_path: Path) -> None:
        self._cache_path = cache_path

    def build_mapping(self, teams: list[dict[str, Any]]) -> dict[int, str]:
        """Build an ID -> name mapping from a bootstrap-static teams list.

        Args:
            teams: Raw team records from
                :meth:`~src.data_collection.sources.fpl_api_source.FPLApiDataSource.get_teams`
                (each must have at least ``id`` and ``name``).

        Returns:
            dict[int, str]: Mapping of team ID to team name.
        """
        mapping = {int(t["id"]): str(t["name"]) for t in teams if "id" in t and "name" in t}
        logger.info("Built team ID -> name mapping for %d team(s).", len(mapping))
        return mapping

    def save(self, mapping: dict[int, str]) -> None:
        """Persist a mapping to the cache path (as ``data/external/team_mapping.json``).

        Args:
            mapping: The mapping to persist.
        """
        ensure_directory(self._cache_path.parent)
        payload = {str(k): v for k, v in mapping.items()}
        self._cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Saved team mapping to %s.", self._cache_path)

    def load(self) -> dict[int, str] | None:
        """Load a previously cached mapping, if one exists.

        Returns:
            dict[int, str] | None: The cached mapping, or ``None`` if
            no cache file exists yet.
        """
        if not self._cache_path.exists():
            return None
        try:
            raw = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return {int(k): v for k, v in raw.items()}
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            logger.warning("Could not read cached team mapping at %s: %s", self._cache_path, exc)
            return None


def resolve_numeric_opponent_column(
    data: pd.DataFrame,
    opponent_column: str,
    mapping: dict[int, str],
) -> tuple[pd.Series, int]:
    """Map a numeric opponent-ID column to team names wherever the mapping covers it.

    Non-numeric values (already team names) are left untouched. Numeric
    values not present in ``mapping`` are left as-is (still numeric) —
    callers should treat those rows as unresolved, not silently correct,
    since guessing would reintroduce the original bug in a new form.

    Args:
        data: The dataset containing ``opponent_column``.
        opponent_column: Column to resolve.
        mapping: Team ID -> name mapping.

    Returns:
        tuple[pd.Series, int]: The resolved column, and a count of how
        many values were successfully mapped from an ID to a name.
    """
    column = data[opponent_column]
    numeric = pd.to_numeric(column, errors="coerce")
    is_numeric = numeric.notna()

    # Cast to object dtype up front: the column may currently be a pure
    # numeric dtype (e.g. int64), which pandas will refuse to accept
    # string values into via .loc[] assignment (raises TypeError /
    # LossySetitemError under strict dtype casting in modern pandas).
    resolved = column.astype(object).copy()
    mapped_values = numeric[is_numeric].map(mapping)
    successfully_mapped = mapped_values.notna()

    resolved.loc[mapped_values.index[successfully_mapped]] = mapped_values[successfully_mapped]
    mapped_count = int(successfully_mapped.sum())

    unmapped_numeric = int(is_numeric.sum()) - mapped_count
    if unmapped_numeric > 0:
        logger.warning(
            "%d numeric value(s) in '%s' had no matching entry in the team mapping "
            "and were left unresolved.",
            unmapped_numeric,
            opponent_column,
        )

    return resolved, mapped_count
