"""Player lookup service.

Kept free of any HTTP-framework dependency so it can be unit tested
directly, and so the API layer stays a thin translation layer over it.
"""

from __future__ import annotations

import pandas as pd

from src.config.logging_config import get_logger
from src.core.exceptions import PlayerNotFoundError

logger = get_logger(__name__)


class PlayerService:
    """Looks up a player's most recently known state.

    Args:
        data: The engineered dataset (Sprint 5 output).
        player_id_columns: Candidate columns identifying a player, in
            priority order. The first one present is used.
        chronological_columns: Candidate columns defining match order,
            used to determine each player's most recent row.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        player_id_columns: tuple[str, ...],
        chronological_columns: tuple[str, ...],
    ) -> None:
        self._player_id_column = next(
            (c for c in player_id_columns if c in data.columns), None
        )
        if self._player_id_column is None:
            raise ValueError(f"No player identifier column found among {player_id_columns}.")

        sort_columns = [c for c in chronological_columns if c in data.columns]
        working = data.sort_values(by=sort_columns, kind="mergesort") if sort_columns else data
        self._latest_rows = (
            working.groupby(self._player_id_column, as_index=False).tail(1).reset_index(drop=True)
        )

    def get_player(self, player_id: str) -> dict:
        """Fetch a player's most recently known state by identifier.

        Args:
            player_id: The player identifier as received from the API
                (a path parameter, so always a string) — compared
                against the resolved identifier column using a
                string-normalized match so both numeric IDs (e.g.
                ``"233"``) and name-based identifiers work.

        Returns:
            dict: The player's latest known row as a JSON-serializable
            dict (NaN values become ``None``).

        Raises:
            PlayerNotFoundError: If no player matches ``player_id``.
        """
        id_as_string = self._latest_rows[self._player_id_column].astype(str)
        matches = self._latest_rows[id_as_string == str(player_id)]

        if matches.empty:
            raise PlayerNotFoundError(f"No player found with identifier '{player_id}'.")

        row = matches.iloc[0]
        return {
            key: (None if pd.isna(value) else _to_native(value)) for key, value in row.items()
        }

    def list_player_ids(self) -> list[str]:
        """List every known player identifier.

        Returns:
            list[str]: All player identifiers, as strings.
        """
        return self._latest_rows[self._player_id_column].astype(str).tolist()


def _to_native(value: object) -> object:
    """Convert a pandas/numpy scalar to a plain Python type for JSON serialization.

    Args:
        value: A scalar value, possibly a numpy/pandas type.

    Returns:
        object: The equivalent built-in Python type.
    """
    if hasattr(value, "item"):
        return value.item()
    return value
