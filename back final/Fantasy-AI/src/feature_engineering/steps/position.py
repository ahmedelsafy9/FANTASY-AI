"""Feature step one-hot encoding player positions with full historical resolution."""

from __future__ import annotations

import glob
from pathlib import Path
import re
import unicodedata

import pandas as pd

from src.config.logging_config import get_logger
from src.feature_engineering.models import FeatureStepSummary
from src.feature_engineering.steps.base import FeatureStep

logger = get_logger(__name__)

_ELEMENT_TYPE_TO_POS: dict[int, str] = {
    1: "GKP",
    2: "DEF",
    3: "MID",
    4: "FWD",
}

_CANONICAL_POSITIONS = ("GKP", "DEF", "MID", "FWD")


def _normalize_name(name: str) -> str:
    """Normalize a player's name into a clean ASCII snake_case identifier."""
    if not isinstance(name, str) or not name.strip():
        return ""
    name_clean = unicodedata.normalize("NFKD", name).encode("ASCII", "ignore").decode("utf-8")
    name_clean = re.sub(r"[^a-zA-Z0-9]", "_", name_clean.lower())
    return re.sub(r"_+", "_", name_clean).strip("_")


class PositionEncodingStep(FeatureStep):
    """Encodes player position into four clean one-hot boolean flags.

    In FPL scoring, position dictates scoring rules (e.g. clean sheet
    points for GKP/DEF, goal bonus differences). This step ensures 100%
    coverage across all historical seasons by resolving positions through:

    1. Direct ``(season, element)`` lookup in raw season metadata
       (``data/raw/vaastav/data/<season>/players_raw.csv``).
    2. The row's existing ``position`` column if valid.
    3. Cross-season player mode position by ``name_normalized``.
    4. Safe fallback to ``"MID"``.

    Note: an earlier version of step 4 fell back to "GKP" when the
    current row's own ``saves`` count was > 0. That was a (minor)
    leakage bug: ``saves`` is a same-match outcome stat, so using it
    to assign a categorical label let a sliver of same-match
    information leak into a feature. It has been removed — the
    fallback is now a fixed default with no dependence on any
    current-row statistic.

    Output columns:
    - ``is_position_gkp``: 1.0 if Goalkeeper, 0.0 otherwise.
    - ``is_position_def``: 1.0 if Defender, 0.0 otherwise.
    - ``is_position_mid``: 1.0 if Midfielder, 0.0 otherwise.
    - ``is_position_fwd``: 1.0 if Forward, 0.0 otherwise.

    Args:
        position_column: Column name holding position strings if present.
        season_column: Column name holding the season identifier.
        element_column: Column name holding the player's season element ID.
        name_column: Column name holding the player's normalized name.
        raw_data_dir: Path to the raw vaastav data directory.
    """

    def __init__(
        self,
        position_column: str = "position",
        season_column: str = "season",
        element_column: str = "element",
        name_column: str = "name_normalized",
        raw_data_dir: Path | str | None = None,
    ) -> None:
        self._position_column = position_column
        self._season_column = season_column
        self._element_column = element_column
        self._name_column = name_column
        self._raw_data_dir = (
            Path(raw_data_dir)
            if raw_data_dir is not None
            else Path("data/raw/vaastav/data")
        )
        self._season_element_map: dict[tuple[str, int], str] | None = None
        self._name_pos_map: dict[str, str] | None = None

    @property
    def name(self) -> str:
        """A short, human-readable identifier for this step."""
        return "position_encoding"

    _COL_GKP = "is_position_gkp"
    _COL_DEF = "is_position_def"
    _COL_MID = "is_position_mid"
    _COL_FWD = "is_position_fwd"

    _OUTPUT_COLUMNS = [_COL_GKP, _COL_DEF, _COL_MID, _COL_FWD]

    def _load_raw_position_maps(self) -> None:
        """Build (season, element) -> position and name -> position lookup caches."""
        if self._season_element_map is not None:
            return

        self._season_element_map = {}
        self._name_pos_map = {}

        if not self._raw_data_dir.exists():
            logger.debug(
                "Raw data directory '%s' does not exist; relying on in-memory columns.",
                self._raw_data_dir,
            )
            return

        pattern = str(self._raw_data_dir / "*" / "players_raw.csv")
        for fpath in glob.glob(pattern):
            p = Path(fpath)
            season = p.parent.name
            try:
                try:
                    df = pd.read_csv(fpath, encoding="utf-8")
                except UnicodeDecodeError:
                    df = pd.read_csv(fpath, encoding="latin1")

                for _, row in df.iterrows():
                    elem_id = row.get("id")
                    etype = row.get("element_type")
                    if pd.notna(elem_id) and pd.notna(etype):
                        try:
                            pos = _ELEMENT_TYPE_TO_POS.get(int(etype))
                            if pos:
                                self._season_element_map[(season, int(elem_id))] = pos
                                fn = str(row.get("first_name", ""))
                                sn = str(row.get("second_name", ""))
                                full_norm = _normalize_name(f"{fn}_{sn}")
                                if full_norm:
                                    self._name_pos_map[full_norm] = pos
                        except (ValueError, TypeError):
                            pass
            except Exception as exc:
                logger.debug("Failed reading %s: %s", fpath, exc)

        logger.debug(
            "Loaded %d (season, element) position mappings and %d name mappings from raw data.",
            len(self._season_element_map),
            len(self._name_pos_map),
        )

    def apply(self, data: pd.DataFrame) -> tuple[pd.DataFrame, FeatureStepSummary]:
        """One-hot encode player positions across all rows.

        Args:
            data: The DataFrame to derive features from.

        Returns:
            tuple[pd.DataFrame, FeatureStepSummary]: The data with the 4 position columns added.
        """
        rows_before = len(data)
        working = data.copy()

        self._load_raw_position_maps()

        # Step 1: Start with existing position column if present
        resolved_pos: pd.Series = pd.Series(None, index=working.index, dtype="object")

        if self._position_column in working.columns:
            cleaned = (
                working[self._position_column]
                .astype(str)
                .str.strip()
                .str.upper()
                .replace({"GK": "GKP", "AM": "MID", "NAN": None, "NONE": None, "": None})
            )
            valid_mask = cleaned.isin(_CANONICAL_POSITIONS)
            resolved_pos = resolved_pos.mask(valid_mask, cleaned)

        # Step 2: Fill from (season, element) lookup
        if (
            self._season_element_map
            and self._season_column in working.columns
            and self._element_column in working.columns
        ):
            missing_mask = resolved_pos.isna()
            if missing_mask.any():
                lookup_keys = list(
                    zip(
                        working.loc[missing_mask, self._season_column].astype(str),
                        pd.to_numeric(working.loc[missing_mask, self._element_column], errors="coerce").fillna(-1).astype(int),
                    )
                )
                from_lookup = [self._season_element_map.get(k) for k in lookup_keys]
                resolved_pos.loc[missing_mask] = pd.Series(
                    from_lookup, index=working.loc[missing_mask].index
                )

        # Step 3: Fill from name_normalized lookup
        if self._name_pos_map:
            name_col = self._name_column if self._name_column in working.columns else "name"
            if name_col in working.columns:
                missing_mask = resolved_pos.isna()
                if missing_mask.any():
                    norm_names = working.loc[missing_mask, name_col].astype(str).map(_normalize_name)
                    from_name = norm_names.map(self._name_pos_map)
                    resolved_pos.loc[missing_mask] = from_name

        # Step 4: Safe default fallback. Deliberately does NOT use any
        # current-row match-outcome statistic (e.g. "saves") to avoid
        # leaking same-match information into a categorical feature.
        resolved_pos = resolved_pos.fillna("MID")

        # Emit 4 one-hot columns
        working[self._COL_GKP] = (resolved_pos == "GKP").astype(float)
        working[self._COL_DEF] = (resolved_pos == "DEF").astype(float)
        working[self._COL_MID] = (resolved_pos == "MID").astype(float)
        working[self._COL_FWD] = (resolved_pos == "FWD").astype(float)

        working.index = data.index

        description = f"Added {len(self._OUTPUT_COLUMNS)} one-hot position column(s)."
        logger.info(description)

        return working, FeatureStepSummary(
            step_name=self.name,
            rows_before=rows_before,
            rows_after=len(working),
            columns_added=list(self._OUTPUT_COLUMNS),
            description=description,
        )
