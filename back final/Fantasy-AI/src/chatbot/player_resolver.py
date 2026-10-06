"""Fuzzy player name resolution for chatbot queries.

Users refer to players in many ways:
  - Web name:  "Palmer", "Salah", "Saka"
  - Full name: "Cole Palmer", "Mohamed Salah"
  - Arabic:    "بالمر", "صلاح", "ساكا"
  - Partial:   "Mo Salah", "KDB"
  - Nickname:  "Haaland", "Bruno"

This module resolves any of those to matching player rows from the
predictions DataFrame.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

import pandas as pd


def _normalize_arabic(text: str) -> str:
    """Normalize Arabic characters and strip diacritics."""
    # Strip tashkeel / harakat
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    # Unify alef forms
    text = re.sub(r"[أإآٱ]", "ا", text)
    # Unify teh marbuta
    text = re.sub(r"ة", "ه", text)
    # Unify alef maksura to yeh
    text = re.sub(r"ى", "ي", text)
    return text.strip().lower()


_PLAYER_ALIASES: dict[str, str] = {
    # English nicknames & abbreviations
    "kdb": "de bruyne",
    "kevin de bruyne": "de bruyne",
    "taa": "alexander-arnold",
    "trent": "alexander-arnold",
    "mo salah": "salah",
    "bruno": "bruno fernandes",
    "vvd": "van dijk",
    # Arabic transliterations
    "صلاح": "salah",
    "محمد صلاح": "mohamed salah",
    "هالاند": "haaland",
    "ارلينغ هالاند": "haaland",
    "بالمر": "palmer",
    "كول بالمر": "cole palmer",
    "ساكا": "saka",
    "بوكايو ساكا": "saka",
    "سون": "son",
    "دي بروين": "de bruyne",
    "كيفين دي بروين": "de bruyne",
    "فودين": "foden",
    "فودن": "foden",
    "واتكينز": "watkins",
    "ايزاك": "isak",
    "إيزاك": "isak",
    "راشفورد": "rashford",
    "فيرنانديز": "bruno fernandes",
    "فان دايك": "van dijk",
    "ساليبا": "saliba",
    "صاليبا": "saliba",
    "سليبا": "saliba",
    "غابرييل": "gabriel",
    "جابرييل": "gabriel",
    "رايا": "raya",
    "بيكفورد": "pickford",
    "ماديسون": "maddison",
    "غوردون": "gordon",
    "جوردون": "gordon",
    "ايزي": "eze",
    "مارتينيلي": "martinelli",
    "هافرتز": "havertz",
    "هافيرتز": "havertz",
    "جاكسون": "jackson",
    "أليسون": "alisson",
    "اليسون": "alisson",
    "دياز": "diaz",
    "رودري": "rodri",
    "برناردو": "bernardo silva",
    "بيدرو": "joao pedro",
    "جواو بيدرو": "joao pedro",
    "سولانكي": "solanke",
    "كودوس": "kudus",
    "قدوس": "kudus",
    "بورو": "porro",
    "جفارديول": "gvardiol",
    "كونيا": "cunha",
    "مبيومو": "mbeumo",
    "ويسا": "wissa",
    "وود": "wood",
    "كريس وود": "wood",
    "ماتيتا": "mateta",
    "ميتوما": "mitoma",
    "سيمينيو": "semenyo",
    "روجرز": "rogers",
    "ديلاب": "delap",
}


def _normalize(text: str) -> str:
    """ASCII-fold and lowercase a string for fuzzy matching."""
    # NFD decompose → strip combining marks → lowercase
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(
        ch for ch in decomposed if unicodedata.category(ch) != "Mn"
    )
    return stripped.lower().strip()


class PlayerResolver:
    """Resolves free-text player queries to matching prediction rows.

    Args:
        predictions: The full predictions DataFrame from AppState.
    """

    def __init__(self, predictions: pd.DataFrame) -> None:
        self._predictions = predictions
        self._build_index()

    def _build_index(self) -> None:
        """Build normalised name lookup indices."""
        self._norm_web: dict[str, list[int]] = {}
        self._norm_full: dict[str, list[int]] = {}
        self._norm_first: dict[str, list[int]] = {}
        self._norm_second: dict[str, list[int]] = {}

        for idx, row in self._predictions.iterrows():
            i = int(idx)
            web = row.get("web_name") or row.get("name") or ""
            first = row.get("first_name") or ""
            second = row.get("second_name") or ""
            full = f"{first} {second}".strip()

            nw = _normalize(str(web))
            nfull = _normalize(str(full))
            nfirst = _normalize(str(first))
            nsecond = _normalize(str(second))

            if nw:
                self._norm_web.setdefault(nw, []).append(i)
            if nfull:
                self._norm_full.setdefault(nfull, []).append(i)
            if nfirst:
                self._norm_first.setdefault(nfirst, []).append(i)
            if nsecond:
                self._norm_second.setdefault(nsecond, []).append(i)

    def resolve(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Resolve a player query to matching rows.

        Match strategy (in priority order):
        1. Exact match on web_name (normalised)
        2. Exact match on full name (normalised)
        3. Exact match on second_name (normalised)
        4. Substring match on web_name
        5. Substring match on full name

        Args:
            query: Free-text player query (any language).
            max_results: Maximum number of matches to return.

        Returns:
            A list of dicts (player rows), best matches first.
        """
        if not query or not query.strip():
            return []

        norm_q = _normalize(query)
        if not norm_q:
            return []

        matched_indices: list[int] = []
        seen: set[int] = set()

        def _add(indices: list[int]) -> None:
            for i in indices:
                if i not in seen:
                    seen.add(i)
                    matched_indices.append(i)

        # 0. Check alias / transliteration mapping (e.g. "صلاح" -> "salah", "kdb" -> "de bruyne")
        norm_ar = _normalize_arabic(query)
        alias_target = _PLAYER_ALIASES.get(norm_q) or _PLAYER_ALIASES.get(norm_ar)
        if alias_target:
            target_norm = _normalize(alias_target)
            if target_norm in self._norm_web:
                _add(self._norm_web[target_norm])
            if target_norm in self._norm_second:
                _add(self._norm_second[target_norm])
            if target_norm in self._norm_full:
                _add(self._norm_full[target_norm])

        # 1. Exact web_name match
        if norm_q in self._norm_web:
            _add(self._norm_web[norm_q])

        # 2. Exact full name match
        if norm_q in self._norm_full:
            _add(self._norm_full[norm_q])

        # 3. Exact second_name match
        if norm_q in self._norm_second:
            _add(self._norm_second[norm_q])

        # 4. Exact first_name match
        if norm_q in self._norm_first:
            _add(self._norm_first[norm_q])

        # 5. Substring match on web_name
        if len(matched_indices) < max_results and len(norm_q) >= 3:
            for nw, indices in self._norm_web.items():
                if norm_q in nw or nw in norm_q:
                    _add(indices)

        # 6. Substring match on full name
        if len(matched_indices) < max_results and len(norm_q) >= 3:
            for nf, indices in self._norm_full.items():
                if norm_q in nf or nf in norm_q:
                    _add(indices)

        # Convert to dicts
        results: list[dict[str, Any]] = []
        for i in matched_indices[:max_results]:
            row = self._predictions.iloc[i]
            results.append(_row_to_safe_dict(row))

        return results

    def resolve_by_id(self, player_id: int) -> dict[str, Any] | None:
        """Resolve a player by their FPL element ID.

        Args:
            player_id: The numeric FPL element ID.

        Returns:
            The player row as a dict, or ``None`` if not found.
        """
        for col in ("element", "id"):
            if col in self._predictions.columns:
                matches = self._predictions[
                    self._predictions[col] == player_id
                ]
                if not matches.empty:
                    return _row_to_safe_dict(matches.iloc[0])
        return None


def _row_to_safe_dict(row: pd.Series) -> dict[str, Any]:
    """Convert a pandas row to a JSON-safe dict."""
    result: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (list, dict)):
            result[key] = value
        elif value is None:
            result[key] = None
        elif hasattr(value, "item"):
            try:
                result[key] = value.item()
            except (ValueError, TypeError):
                result[key] = str(value)
        else:
            try:
                if pd.isna(value):
                    result[key] = None
                    continue
            except (ValueError, TypeError):
                pass
            result[key] = value
    return result
