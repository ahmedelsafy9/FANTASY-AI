"""Budget-Aware Two-Stage Optimization Service for Fantasy-AI Squad Builder.

Constructs a complete, valid, 15-player FPL squad (2 GKP, 5 DEF, 5 MID, 3 FWD)
within the configured budget (default £100.0m) and max 3 players per club.

Algorithm:
1. Feasibility check before every selection:
   remaining_budget - price >= minimum_cost_to_fill_remaining_slots
2. Stage 1: Core high-point picks (prioritizing predicted points/rank score).
3. Stage 2: Value-for-money completion (prioritizing points per million + points).
4. Backtracking & Repair: If early core picks cause infeasibility, downgrade
   expensive picks to restore feasibility.
5. Final Local Optimization Pass: Efficiently utilizes remaining unspent budget
   via 1-for-1 player upgrades without exceeding budget.
6. Designates Starting XI, Bench, Captain, and Vice-Captain.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from src.api.schemas import SquadBuildResponse, SquadPlayer
from src.config.logging_config import get_logger
from src.core.exceptions import SquadBuilderError

logger = get_logger(__name__)

POSITION_LIMITS: dict[str, int] = {
    "GKP": 2,
    "DEF": 5,
    "MID": 5,
    "FWD": 3,
}

SQUAD_SIZE: int = 15
DEFAULT_BUDGET: float = 100.0
MAX_PER_TEAM: int = 3


def normalize_pos(pos: str | None) -> str:
    """Normalize position string to GKP, DEF, MID, or FWD."""
    if not pos:
        return "MID"
    p = str(pos).strip().upper()
    if p in ("GK", "GKP", "GOALKEEPER", "1"):
        return "GKP"
    if p in ("DEF", "DEFENDER", "2"):
        return "DEF"
    if p in ("MID", "MIDFIELDER", "3"):
        return "MID"
    if p in ("FWD", "FORWARD", "ATTACKER", "4"):
        return "FWD"
    return p


def parse_formation(formation_str: str) -> tuple[int, int, int]:
    """Parse a formation string e.g. '4-4-2' into (def, mid, fwd)."""
    parts = formation_str.split("-")
    if len(parts) == 3:
        try:
            d, m, f = int(parts[0]), int(parts[1]), int(parts[2])
            if 3 <= d <= 5 and 2 <= m <= 5 and 1 <= f <= 3 and (d + m + f == 10):
                return d, m, f
        except ValueError:
            pass
    return 4, 4, 2


@dataclass
class CandidatePlayer:
    """Internal candidate representation for squad optimization."""

    element: int | None
    name: str
    position: str
    team: str
    price: float
    value: float | None
    predicted_points: float
    predicted_expected_points: float | None
    predicted_fpl_rank_score: float | None
    points_per_million: float
    value_score: float
    photo_url: str | None
    raw_row: dict[str, Any]

    @property
    def pid(self) -> str:
        return str(self.element) if self.element is not None else self.name


class SquadBuilderService:
    """Service that builds an optimal FPL squad within budget constraints."""

    def __init__(self, predictions: pd.DataFrame) -> None:
        self._predictions = predictions

    def build_squad(
        self,
        budget: float = DEFAULT_BUDGET,
        formation: str = "4-4-2",
        core_picks_count: int = 4,
        season: str | None = None,
        gameweek: int | None = None,
    ) -> SquadBuildResponse:
        """Construct a complete, optimal, valid 15-player squad within budget.

        Args:
            budget: Total spending limit in £M (default: 100.0).
            formation: Preferred starting XI formation (e.g. '4-4-2', '3-5-2').
            core_picks_count: Number of premium core picks to attempt.
            season: Current FPL season.
            gameweek: Target gameweek.

        Returns:
            SquadBuildResponse with full squad, starters, bench, and metadata.

        Raises:
            SquadBuilderError: If no valid squad can be constructed.
        """
        candidates = self._prepare_candidates()
        if len(candidates) < SQUAD_SIZE:
            raise SquadBuilderError(
                f"Candidate pool contains only {len(candidates)} players, "
                f"minimum {SQUAD_SIZE} required."
            )

        # Segregate by position
        pos_candidates: dict[str, list[CandidatePlayer]] = {
            pos: [c for c in candidates if c.position == pos]
            for pos in ("GKP", "DEF", "MID", "FWD")
        }

        # Check sufficient candidates in each position
        for pos, limit in POSITION_LIMITS.items():
            if len(pos_candidates[pos]) < limit:
                raise SquadBuilderError(
                    f"Insufficient players in position {pos}: "
                    f"available {len(pos_candidates[pos])}, required {limit}."
                )

        # Calculate minimum possible cost to field 15 players
        cheapest_by_pos: dict[str, list[float]] = {
            pos: sorted([c.price for c in pos_candidates[pos]])
            for pos in ("GKP", "DEF", "MID", "FWD")
        }
        abs_min_cost = sum(
            sum(cheapest_by_pos[pos][: POSITION_LIMITS[pos]])
            for pos in ("GKP", "DEF", "MID", "FWD")
        )

        if budget < abs_min_cost - 1e-4:
            raise SquadBuilderError(
                f"Budget of £{budget:.1f}m is insufficient to construct a valid squad. "
                f"Minimum cost to field 15 players is £{abs_min_cost:.1f}m."
            )

        # Run Two-Stage Optimization with Backtracking
        selected_candidates, selection_meta = self._optimize_squad(
            pos_candidates=pos_candidates,
            budget=budget,
            target_core_count=core_picks_count,
        )

        # Local Improvement Pass using remaining budget
        selected_candidates, selection_meta = self._local_optimization_pass(
            selected_candidates=selected_candidates,
            selection_meta=selection_meta,
            pos_candidates=pos_candidates,
            budget=budget,
        )

        # Convert to response SquadPlayer models
        total_cost = sum(c.price for c in selected_candidates)
        remaining_budget = max(0.0, round(budget - total_cost, 2))
        total_predicted_points = sum(c.predicted_points for c in selected_candidates)

        # Assign Starters, Bench, Captain, Vice-Captain
        start_def, start_mid, start_fwd = parse_formation(formation)
        starting_xi_candidates, bench_candidates = self._select_starters_and_bench(
            selected_candidates, start_def, start_mid, start_fwd
        )

        # Sort starting XI by predicted points to find Captain & Vice-Captain
        sorted_starters = sorted(
            starting_xi_candidates, key=lambda c: c.predicted_points, reverse=True
        )
        captain_id = sorted_starters[0].pid
        vice_captain_id = sorted_starters[1].pid if len(sorted_starters) > 1 else None

        # Build final SquadPlayer objects
        squad_players: list[SquadPlayer] = []
        starting_xi: list[SquadPlayer] = []
        bench: list[SquadPlayer] = []
        core_picks: list[SquadPlayer] = []
        value_picks: list[SquadPlayer] = []

        for c in selected_candidates:
            is_start = c in starting_xi_candidates
            is_cap = c.pid == captain_id
            is_vc = c.pid == vice_captain_id
            meta = selection_meta.get(
                c.pid,
                {"type": "value", "reason": "Value Pick: Strong expected points per £m"},
            )

            sp = SquadPlayer(
                element=c.element,
                name=c.name,
                position=c.position,
                team=c.team,
                price=c.price,
                value=c.value,
                predicted_points=round(c.predicted_points, 2),
                predicted_expected_points=(
                    round(c.predicted_expected_points, 2)
                    if c.predicted_expected_points is not None
                    else None
                ),
                predicted_fpl_rank_score=(
                    round(c.predicted_fpl_rank_score, 2)
                    if c.predicted_fpl_rank_score is not None
                    else None
                ),
                points_per_million=round(c.points_per_million, 2),
                selection_type=meta["type"],
                selection_reason=meta["reason"],
                is_starter=is_start,
                is_captain=is_cap,
                is_vice_captain=is_vc,
                photo_url=c.photo_url,
            )
            squad_players.append(sp)
            if is_start:
                starting_xi.append(sp)
            else:
                bench.append(sp)

            if meta["type"] == "core":
                core_picks.append(sp)
            else:
                value_picks.append(sp)

        captain_player = next(p for p in squad_players if p.is_captain)
        vice_captain_player = next(p for p in squad_players if p.is_vice_captain)

        return SquadBuildResponse(
            season=season,
            gameweek=gameweek,
            budget=budget,
            total_cost=round(total_cost, 1),
            remaining_budget=remaining_budget,
            total_predicted_points=round(total_predicted_points, 2),
            formation=formation,
            count=len(squad_players),
            captain=captain_player,
            vice_captain=vice_captain_player,
            starting_xi=starting_xi,
            bench=bench,
            squad=squad_players,
            core_picks=core_picks,
            value_picks=value_picks,
        )

    def _prepare_candidates(self) -> list[CandidatePlayer]:
        """Transform raw prediction rows into normalized CandidatePlayer list."""
        candidates: list[CandidatePlayer] = []
        if self._predictions is None or self._predictions.empty:
            return candidates

        for _, row in self._predictions.iterrows():
            pos = normalize_pos(row.get("position"))
            if pos not in ("GKP", "DEF", "MID", "FWD"):
                continue

            raw_cost = row.get("now_cost")
            if raw_cost is None or pd.isna(raw_cost):
                raw_cost = row.get("value")
            try:
                val = float(raw_cost) if raw_cost is not None else 0.0
            except (ValueError, TypeError):
                val = 0.0

            if val <= 0:
                continue

            price = round(val / 10.0, 1)

            # Authoritative predicted points priority: rank_score -> expected_points -> total_points
            rank_score = row.get("predicted_fpl_rank_score")
            exp_pts = row.get("predicted_expected_points")
            tot_pts = row.get("predicted_total_points")

            pts = 0.0
            if rank_score is not None and not pd.isna(rank_score):
                pts = float(rank_score)
            elif exp_pts is not None and not pd.isna(exp_pts):
                pts = float(exp_pts)
            elif tot_pts is not None and not pd.isna(tot_pts):
                pts = float(tot_pts)

            ppm = pts / price if price > 0 else 0.0
            # Blended value score: high points-per-million with weight for raw points
            value_score = (0.7 * ppm) + (0.3 * pts)

            element_val = row.get("element")
            element = int(element_val) if element_val is not None and not pd.isna(element_val) else None
            name = str(row.get("name", "Unknown"))
            team = str(row.get("team", "Unknown"))
            photo_url = str(row.get("photo_url")) if row.get("photo_url") and not pd.isna(row.get("photo_url")) else None

            candidates.append(
                CandidatePlayer(
                    element=element,
                    name=name,
                    position=pos,
                    team=team,
                    price=price,
                    value=val,
                    predicted_points=pts,
                    predicted_expected_points=float(exp_pts) if exp_pts is not None and not pd.isna(exp_pts) else None,
                    predicted_fpl_rank_score=float(rank_score) if rank_score is not None and not pd.isna(rank_score) else None,
                    points_per_million=ppm,
                    value_score=value_score,
                    photo_url=photo_url,
                    raw_row=dict(row),
                )
            )

        return candidates

    def _calculate_minimum_remaining_cost(
        self,
        current_pos_counts: dict[str, int],
        pos_candidates: dict[str, list[CandidatePlayer]],
        selected_pids: set[str],
        club_counts: dict[str, int],
    ) -> float:
        """Calculate the absolute minimum cost to fill remaining required slots."""
        total_min_cost = 0.0

        for pos, req_count in POSITION_LIMITS.items():
            needed = req_count - current_pos_counts[pos]
            if needed <= 0:
                continue

            # Eligible candidates in this position not already selected
            eligible = [
                c.price
                for c in pos_candidates[pos]
                if c.pid not in selected_pids and club_counts.get(c.team, 0) < MAX_PER_TEAM
            ]
            eligible.sort()

            if len(eligible) < needed:
                # Impossible to fill this position
                return float("inf")

            total_min_cost += sum(eligible[:needed])

        return total_min_cost

    def _is_feasible(
        self,
        candidate: CandidatePlayer,
        selected: list[CandidatePlayer],
        pos_candidates: dict[str, list[CandidatePlayer]],
        budget: float,
    ) -> bool:
        """Check if adding candidate preserves budget and constraints to complete squad."""
        current_pids = {c.pid for c in selected}
        if candidate.pid in current_pids:
            return False

        pos_counts: dict[str, int] = {p: 0 for p in POSITION_LIMITS}
        club_counts: dict[str, int] = {}
        current_cost = 0.0

        for c in selected:
            pos_counts[c.position] += 1
            club_counts[c.team] = club_counts.get(c.team, 0) + 1
            current_cost += c.price

        # Check position limit
        if pos_counts[candidate.position] >= POSITION_LIMITS[candidate.position]:
            return False

        # Check team limit
        if club_counts.get(candidate.team, 0) >= MAX_PER_TEAM:
            return False

        # Check remaining budget feasibility
        cost_after = current_cost + candidate.price
        if cost_after > budget + 1e-4:
            return False

        rem_budget_after = budget - cost_after

        # Tentative new state
        pos_counts[candidate.position] += 1
        club_counts[candidate.team] = club_counts.get(candidate.team, 0) + 1
        current_pids.add(candidate.pid)

        min_remaining_cost = self._calculate_minimum_remaining_cost(
            pos_counts, pos_candidates, current_pids, club_counts
        )

        return rem_budget_after >= min_remaining_cost - 1e-4

    def _optimize_squad(
        self,
        pos_candidates: dict[str, list[CandidatePlayer]],
        budget: float,
        target_core_count: int,
    ) -> tuple[list[CandidatePlayer], dict[str, dict[str, str]]]:
        """Perform two-stage selection with backtracking."""
        # Rank by raw points for Stage 1 Core Picks
        all_candidates = [c for pos in pos_candidates.values() for c in pos]
        core_pool = sorted(all_candidates, key=lambda c: c.predicted_points, reverse=True)

        # Rank by Value (PPM + point weight) for Stage 2 Completion
        value_pos_candidates = {
            pos: sorted(pos_candidates[pos], key=lambda c: c.value_score, reverse=True)
            for pos in pos_candidates
        }

        # Try building with decreasing number of core picks if infeasible
        for core_limit in range(target_core_count, -1, -1):
            selected: list[CandidatePlayer] = []
            selection_meta: dict[str, dict[str, str]] = {}
            core_picks: list[CandidatePlayer] = []

            # Stage 1: Add Core High-Point Picks
            pos_core_limits = {"GKP": 1, "DEF": 2, "MID": 2, "FWD": 2}
            pos_core_counts = {p: 0 for p in POSITION_LIMITS}

            for c in core_pool:
                if len(core_picks) >= core_limit:
                    break
                if pos_core_counts[c.position] >= pos_core_limits[c.position]:
                    continue

                if self._is_feasible(c, selected, pos_candidates, budget):
                    selected.append(c)
                    core_picks.append(c)
                    pos_core_counts[c.position] += 1
                    selection_meta[c.pid] = {
                        "type": "core",
                        "reason": f"Core Pick: High predicted points ({c.predicted_points:.1f} pts)",
                    }

            # Stage 2: Value for Money Completion
            completed = self._complete_squad(
                selected=selected,
                selection_meta=selection_meta,
                value_pos_candidates=value_pos_candidates,
                pos_candidates=pos_candidates,
                budget=budget,
            )

            if completed and len(selected) == SQUAD_SIZE:
                return selected, selection_meta

            # If completion failed with core picks, backtrack / downgrade
            while core_picks and len(selected) < SQUAD_SIZE:
                # Remove most expensive core pick
                expensive_core = max(core_picks, key=lambda c: c.price)
                core_picks.remove(expensive_core)
                selected.remove(expensive_core)
                selection_meta.pop(expensive_core.pid, None)

                # Try completing again
                completed = self._complete_squad(
                    selected=selected,
                    selection_meta=selection_meta,
                    value_pos_candidates=value_pos_candidates,
                    pos_candidates=pos_candidates,
                    budget=budget,
                )
                if completed and len(selected) == SQUAD_SIZE:
                    return selected, selection_meta

        raise SquadBuilderError("Failed to construct a complete valid squad within budget constraints.")

    def _complete_squad(
        self,
        selected: list[CandidatePlayer],
        selection_meta: dict[str, dict[str, str]],
        value_pos_candidates: dict[str, list[CandidatePlayer]],
        pos_candidates: dict[str, list[CandidatePlayer]],
        budget: float,
    ) -> bool:
        """Fill all remaining required squad slots using value-ranked candidates."""
        pos_counts: dict[str, int] = {p: 0 for p in POSITION_LIMITS}
        for c in selected:
            pos_counts[c.position] += 1

        # Fill in order: GKP (2), DEF (5), MID (5), FWD (3)
        for pos in ("GKP", "DEF", "MID", "FWD"):
            needed = POSITION_LIMITS[pos] - pos_counts[pos]
            for _ in range(needed):
                added = False
                for candidate in value_pos_candidates[pos]:
                    if self._is_feasible(candidate, selected, pos_candidates, budget):
                        selected.append(candidate)
                        pos_counts[pos] += 1
                        selection_meta[candidate.pid] = {
                            "type": "value",
                            "reason": f"Value Pick: Strong points-per-£m ({candidate.points_per_million:.1f} ppm)",
                        }
                        added = True
                        break

                if not added:
                    # Fallback to cheapest feasible player in position
                    cheapest_candidates = sorted(pos_candidates[pos], key=lambda c: c.price)
                    for candidate in cheapest_candidates:
                        if self._is_feasible(candidate, selected, pos_candidates, budget):
                            selected.append(candidate)
                            pos_counts[pos] += 1
                            selection_meta[candidate.pid] = {
                                "type": "budget_constraint",
                                "reason": "Budget Constraint: Selected to preserve budget feasibility",
                            }
                            added = True
                            break

                if not added:
                    return False

        return len(selected) == SQUAD_SIZE

    def _local_optimization_pass(
        self,
        selected_candidates: list[CandidatePlayer],
        selection_meta: dict[str, dict[str, str]],
        pos_candidates: dict[str, list[CandidatePlayer]],
        budget: float,
    ) -> tuple[list[CandidatePlayer], dict[str, dict[str, str]]]:
        """Spend remaining unused budget to perform 1-for-1 upgrades that maximize points."""
        selected = list(selected_candidates)
        meta = dict(selection_meta)

        improved = True
        iterations = 0

        while improved and iterations < 15:
            improved = False
            iterations += 1
            current_cost = sum(c.price for c in selected)
            slack = budget - current_cost
            if slack < 0.4:
                break

            current_pids = {c.pid for c in selected}
            club_counts: dict[str, int] = {}
            for c in selected:
                club_counts[c.team] = club_counts.get(c.team, 0) + 1

            best_swap: tuple[CandidatePlayer, CandidatePlayer, float] | None = None
            best_points_gain = 0.0

            # Consider replacing player A with player B in the same position
            for player_a in selected:
                # If replacing A, A's club count drops by 1
                club_after_remove = dict(club_counts)
                club_after_remove[player_a.team] -= 1

                for player_b in pos_candidates[player_a.position]:
                    if player_b.pid in current_pids:
                        continue

                    # Check club limit for B
                    if club_after_remove.get(player_b.team, 0) >= MAX_PER_TEAM:
                        continue

                    cost_diff = player_b.price - player_a.price
                    if cost_diff > slack + 1e-4:
                        continue

                    points_gain = player_b.predicted_points - player_a.predicted_points
                    if points_gain > 0.05 and points_gain > best_points_gain:
                        best_points_gain = points_gain
                        best_swap = (player_a, player_b, points_gain)

            if best_swap:
                old_p, new_p, gain = best_swap
                idx = selected.index(old_p)
                selected[idx] = new_p
                meta.pop(old_p.pid, None)
                meta[new_p.pid] = {
                    "type": "core" if new_p.predicted_points >= 6.0 else "value",
                    "reason": f"Budget Optimization: Upgraded +{gain:.1f} pts within remaining budget",
                }
                improved = True

        return selected, meta

    def _select_starters_and_bench(
        self,
        selected: list[CandidatePlayer],
        target_def: int,
        target_mid: int,
        target_fwd: int,
    ) -> tuple[list[CandidatePlayer], list[CandidatePlayer]]:
        """Select starting XI according to formation and bench players."""
        gkps = [c for c in selected if c.position == "GKP"]
        defs = [c for c in selected if c.position == "DEF"]
        mids = [c for c in selected if c.position == "MID"]
        fwds = [c for c in selected if c.position == "FWD"]

        # Sort each position by predicted points
        gkps.sort(key=lambda c: c.predicted_points, reverse=True)
        defs.sort(key=lambda c: c.predicted_points, reverse=True)
        mids.sort(key=lambda c: c.predicted_points, reverse=True)
        fwds.sort(key=lambda c: c.predicted_points, reverse=True)

        start_gk = gkps[:1]
        bench_gk = gkps[1:]

        start_defs = defs[:target_def]
        bench_defs = defs[target_def:]

        start_mids = mids[:target_mid]
        bench_mids = mids[target_mid:]

        start_fwds = fwds[:target_fwd]
        bench_fwds = fwds[target_fwd:]

        starting_xi = start_gk + start_defs + start_mids + start_fwds
        # Outfield bench sorted by predicted points
        outfield_bench = sorted(
            bench_defs + bench_mids + bench_fwds,
            key=lambda c: c.predicted_points,
            reverse=True,
        )
        bench = bench_gk + outfield_bench

        return starting_xi, bench
