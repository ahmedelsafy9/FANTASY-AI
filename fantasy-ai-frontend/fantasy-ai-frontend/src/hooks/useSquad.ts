import { useCallback, useEffect, useMemo, useState } from "react";
import type { PlayerRecord } from "@/types/api";

const SQUAD_STORAGE_KEY = "fantasy_ai_squad_state_v2";
const SQUAD_SIZE = 15;
export const TOTAL_BUDGET = 100.0; // £100.0m

export const SUPPORTED_FORMATIONS = [
  "4-4-2",
  "4-3-3",
  "3-5-2",
  "3-4-3",
  "5-3-2",
  "5-4-1",
  "4-5-1",
  "5-2-3",
] as const;

export type Formation = (typeof SUPPORTED_FORMATIONS)[number];

export interface FormationStructure {
  def: number;
  mid: number;
  fwd: number;
}

export function parseFormation(formation: string): FormationStructure {
  const parts = formation.split("-").map((p) => parseInt(p, 10));
  if (parts.length === 3 && !parts.some(Number.isNaN)) {
    return { def: parts[0], mid: parts[1], fwd: parts[2] };
  }
  return { def: 4, mid: 4, fwd: 2 };
}

export const POSITION_LIMITS: Record<string, number> = {
  GKP: 2,
  GK: 2,
  DEF: 5,
  MID: 5,
  FWD: 3,
};

export const POSITION_MIN_STARTERS: Record<string, number> = {
  GKP: 1,
  GK: 1,
  DEF: 3,
  MID: 2,
  FWD: 1,
};

export const POSITION_MAX_STARTERS: Record<string, number> = {
  GKP: 1,
  GK: 1,
  DEF: 5,
  MID: 5,
  FWD: 3,
};

/** Normalize position string (e.g. GK -> GKP) */
export function normalizePosition(pos?: string | null): string {
  if (!pos) return "MID";
  const p = pos.toUpperCase().trim();
  if (p === "GK") return "GKP";
  return p;
}

/** Extract price in £M from player record (e.g., 60 => 6.0) */
export function getPlayerPrice(player: PlayerRecord): number {
  const raw = player.value ?? player.now_cost;
  const val = typeof raw === "number" ? raw : Number(raw);
  if (val === null || val === undefined || Number.isNaN(val)) return 0;
  return val / 10;
}

/** Get stable player identifier string/number */
export function getPlayerId(player: PlayerRecord): string {
  if (player.element !== undefined && player.element !== null) {
    return String(player.element);
  }
  return player.name ?? "unknown";
}

export interface AddPlayerResult {
  allowed: boolean;
  reason?: string;
}

interface StoredSquadState {
  squad: PlayerRecord[];
  starterIds: string[];
  formation: Formation;
  captainId: string | null;
  viceCaptainId: string | null;
  benchOrder: string[];
}

export function loadInitialState(): StoredSquadState {
  if (typeof window === "undefined") {
    return {
      squad: [],
      starterIds: [],
      formation: "4-4-2",
      captainId: null,
      viceCaptainId: null,
      benchOrder: [],
    };
  }
  try {
    const raw = localStorage.getItem(SQUAD_STORAGE_KEY);
    if (!raw) {
      return {
        squad: [],
        starterIds: [],
        formation: "4-4-2",
        captainId: null,
        viceCaptainId: null,
        benchOrder: [],
      };
    }
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed.squad)) {
      return {
        squad: parsed.squad,
        starterIds: Array.isArray(parsed.starterIds) ? parsed.starterIds : [],
        formation: SUPPORTED_FORMATIONS.includes(parsed.formation)
          ? parsed.formation
          : "4-4-2",
        captainId: typeof parsed.captainId === "string" ? parsed.captainId : null,
        viceCaptainId:
          typeof parsed.viceCaptainId === "string" ? parsed.viceCaptainId : null,
        benchOrder: Array.isArray(parsed.benchOrder) ? parsed.benchOrder : [],
      };
    }
  } catch {
    // Fall back to clean state if JSON corrupted
  }
  return {
    squad: [],
    starterIds: [],
    formation: "4-4-2",
    captainId: null,
    viceCaptainId: null,
    benchOrder: [],
  };
}

export function useSquad() {
  const [initial] = useState(loadInitialState);
  const [squad, setSquad] = useState<PlayerRecord[]>(initial.squad);
  const [starterIds, setStarterIds] = useState<string[]>(initial.starterIds);
  const [formation, setFormationState] = useState<Formation>(initial.formation);
  const [captainId, setCaptainId] = useState<string | null>(initial.captainId);
  const [viceCaptainId, setViceCaptainId] = useState<string | null>(initial.viceCaptainId);
  const [benchOrder, setBenchOrder] = useState<string[]>(initial.benchOrder);

  // Persist squad state to localStorage
  useEffect(() => {
    try {
      const stateToSave: StoredSquadState = {
        squad,
        starterIds,
        formation,
        captainId,
        viceCaptainId,
        benchOrder,
      };
      localStorage.setItem(SQUAD_STORAGE_KEY, JSON.stringify(stateToSave));
    } catch {
      // Ignore localStorage errors (e.g. private browsing quota)
    }
  }, [squad, starterIds, formation, captainId, viceCaptainId, benchOrder]);

  const isInSquad = useCallback(
    (player: PlayerRecord) => {
      const pid = getPlayerId(player);
      return squad.some((p) => getPlayerId(p) === pid);
    },
    [squad],
  );

  const getPositionCounts = useCallback((squadList: PlayerRecord[]) => {
    const counts: Record<string, number> = { GKP: 0, DEF: 0, MID: 0, FWD: 0 };
    for (const p of squadList) {
      const pos = normalizePosition(p.position);
      counts[pos] = (counts[pos] || 0) + 1;
    }
    return counts;
  }, []);

  const getClubCounts = useCallback((squadList: PlayerRecord[]) => {
    const counts: Record<string, number> = {};
    for (const p of squadList) {
      if (p.team) {
        counts[p.team] = (counts[p.team] || 0) + 1;
      }
    }
    return counts;
  }, []);

  const totalSquadPrice = useMemo(() => {
    return squad.reduce((sum, p) => sum + getPlayerPrice(p), 0);
  }, [squad]);

  const remainingBudget = useMemo(() => {
    return Math.max(0, TOTAL_BUDGET - totalSquadPrice);
  }, [totalSquadPrice]);

  const canAddPlayer = useCallback(
    (player: PlayerRecord, options?: { targetPosition?: string }): AddPlayerResult => {
      const pid = getPlayerId(player);
      if (squad.some((p) => getPlayerId(p) === pid)) {
        return { allowed: false, reason: "Already in your squad" };
      }
      if (squad.length >= SQUAD_SIZE) {
        return { allowed: false, reason: "Squad is full (15/15)" };
      }

      const playerPos = normalizePosition(player.position);
      if (options?.targetPosition) {
        const requiredPos = normalizePosition(options.targetPosition);
        if (playerPos !== requiredPos) {
          const label =
            requiredPos === "GKP"
              ? "Goalkeeper"
              : requiredPos === "DEF"
                ? "Defender"
                : requiredPos === "MID"
                  ? "Midfielder"
                  : "Forward";
          return { allowed: false, reason: `Slot requires a ${label}` };
        }
      }

      const price = getPlayerPrice(player);
      if (price > remainingBudget + 0.001) {
        return {
          allowed: false,
          reason: `Requires £${price.toFixed(1)}m (Remaining: £${remainingBudget.toFixed(1)}m)`,
        };
      }

      const posCounts = getPositionCounts(squad);
      const posLimit = POSITION_LIMITS[playerPos] ?? 5;
      if ((posCounts[playerPos] || 0) >= posLimit) {
        const label =
          playerPos === "GKP"
            ? "Goalkeepers"
            : playerPos === "DEF"
              ? "Defenders"
              : playerPos === "MID"
                ? "Midfielders"
                : "Forwards";
        return { allowed: false, reason: `Max ${posLimit} ${label} allowed in squad` };
      }

      if (player.team) {
        const clubCounts = getClubCounts(squad);
        if ((clubCounts[player.team] || 0) >= 3) {
          return { allowed: false, reason: `Max 3 players from ${player.team}` };
        }
      }

      return { allowed: true };
    },
    [squad, remainingBudget, getPositionCounts, getClubCounts],
  );

  const canReplacePlayer = useCallback(
    (oldPlayer: PlayerRecord, newPlayer: PlayerRecord): AddPlayerResult => {
      const oldPid = getPlayerId(oldPlayer);
      const newPid = getPlayerId(newPlayer);

      if (oldPid === newPid) {
        return { allowed: false, reason: "Same player" };
      }

      if (squad.some((p) => getPlayerId(p) === newPid && getPlayerId(p) !== oldPid)) {
        return { allowed: false, reason: "Already in squad" };
      }

      const oldPos = normalizePosition(oldPlayer.position);
      const newPos = normalizePosition(newPlayer.position);
      if (oldPos !== newPos) {
        return { allowed: false, reason: `Cannot replace a ${oldPos} with a ${newPos}` };
      }

      const oldPrice = getPlayerPrice(oldPlayer);
      const newPrice = getPlayerPrice(newPlayer);
      const effectiveBudget = remainingBudget + oldPrice;

      if (newPrice > effectiveBudget + 0.001) {
        return {
          allowed: false,
          reason: `Requires £${newPrice.toFixed(1)}m (Available: £${effectiveBudget.toFixed(1)}m)`,
        };
      }

      if (newPlayer.team && newPlayer.team !== oldPlayer.team) {
        const clubCounts = getClubCounts(squad);
        if ((clubCounts[newPlayer.team] || 0) >= 3) {
          return { allowed: false, reason: `Max 3 players from ${newPlayer.team}` };
        }
      }

      return { allowed: true };
    },
    [squad, remainingBudget, getClubCounts],
  );

  const addPlayer = useCallback(
    (player: PlayerRecord, options?: { asStarter?: boolean; targetPosition?: string }): boolean => {
      const check = canAddPlayer(player, options);
      if (!check.allowed) return false;

      const pid = getPlayerId(player);
      setSquad((current) => [...current, player]);

      if (options?.asStarter) {
        setStarterIds((ids) => [...ids, pid]);
      }
      return true;
    },
    [canAddPlayer],
  );

  const removePlayer = useCallback((player: PlayerRecord) => {
    const pid = getPlayerId(player);
    setSquad((current) => current.filter((p) => getPlayerId(p) !== pid));
    setStarterIds((ids) => ids.filter((id) => id !== pid));
    setBenchOrder((order) => order.filter((id) => id !== pid));
    setCaptainId((cid) => (cid === pid ? null : cid));
    setViceCaptainId((vcid) => (vcid === pid ? null : vcid));
  }, []);

  const replacePlayer = useCallback(
    (oldPlayer: PlayerRecord, newPlayer: PlayerRecord): { success: boolean; reason?: string } => {
      const check = canReplacePlayer(oldPlayer, newPlayer);
      if (!check.allowed) {
        return { success: false, reason: check.reason };
      }

      const oldPid = getPlayerId(oldPlayer);
      const newPid = getPlayerId(newPlayer);

      setSquad((current) =>
        current.map((p) => (getPlayerId(p) === oldPid ? newPlayer : p)),
      );

      setStarterIds((ids) => ids.map((id) => (id === oldPid ? newPid : id)));
      setBenchOrder((order) => order.map((id) => (id === oldPid ? newPid : id)));

      setCaptainId((cid) => (cid === oldPid ? newPid : cid));
      setViceCaptainId((vcid) => (vcid === oldPid ? newPid : vcid));

      return { success: true };
    },
    [canReplacePlayer],
  );

  const togglePlayer = useCallback(
    (player: PlayerRecord): boolean => {
      if (isInSquad(player)) {
        removePlayer(player);
        return true;
      }
      return addPlayer(player);
    },
    [isInSquad, removePlayer, addPlayer],
  );

  const resetSquad = useCallback(() => {
    setSquad([]);
    setStarterIds([]);
    setCaptainId(null);
    setViceCaptainId(null);
    setBenchOrder([]);
    localStorage.removeItem(SQUAD_STORAGE_KEY);
  }, []);

  // Compute Starting XI and Bench dynamically derived:
  // Bench = FULL SQUAD (15) - STARTING XI (11)
  const {
    startingXI,
    bench,
    formationStr,
    effectiveCaptain,
    effectiveViceCaptain,
    totalStartingXp,
    totalSquadXp,
    isValidSquad,
    validationErrors,
  } = useMemo(() => {
    if (squad.length === 0) {
      return {
        startingXI: [],
        bench: [],
        formationStr: formation,
        effectiveCaptain: null,
        effectiveViceCaptain: null,
        totalStartingXp: 0,
        totalSquadXp: 0,
        isValidSquad: false,
        validationErrors: ["Squad is empty."],
      };
    }

    const sortFn = (a: PlayerRecord, b: PlayerRecord) =>
      (b.predicted_total_points ?? -100) - (a.predicted_total_points ?? -100);

    const validStarterIds = starterIds.filter((id) =>
      squad.some((p) => getPlayerId(p) === id),
    );

    let startingXIList: PlayerRecord[] = [];
    let benchList: PlayerRecord[] = [];

    const gkps = squad.filter((p) => normalizePosition(p.position) === "GKP");
    const defs = squad.filter((p) => normalizePosition(p.position) === "DEF");
    const mids = squad.filter((p) => normalizePosition(p.position) === "MID");
    const fwds = squad.filter((p) => normalizePosition(p.position) === "FWD");

    const targetStructure = parseFormation(formation);

    if (validStarterIds.length > 0) {
      startingXIList = squad.filter((p) => validStarterIds.includes(getPlayerId(p)));
      const startingIdsSet = new Set(startingXIList.map(getPlayerId));

      // Bench is simply all remaining players not in Starting XI
      const benchGkps = gkps.filter((p) => !startingIdsSet.has(getPlayerId(p)));
      const benchOutfield = squad.filter(
        (p) => normalizePosition(p.position) !== "GKP" && !startingIdsSet.has(getPlayerId(p)),
      );

      // Order outfield bench according to benchOrder priority, otherwise sorted by points
      const orderedOutfield = [...benchOutfield].sort((a, b) => {
        const idxA = benchOrder.indexOf(getPlayerId(a));
        const idxB = benchOrder.indexOf(getPlayerId(b));
        if (idxA !== -1 && idxB !== -1) return idxA - idxB;
        if (idxA !== -1) return -1;
        if (idxB !== -1) return 1;
        return sortFn(a, b);
      });

      // Slot 0 is always the backup GK, followed by the 3 outfield substitutes
      benchList = [...benchGkps, ...orderedOutfield];
    } else {
      // Automatic derivation matching formation target
      const sortedGkps = [...gkps].sort(sortFn);
      const startGkp = sortedGkps.slice(0, 1);
      const benchGkp = sortedGkps.slice(1);

      const sortedDefs = [...defs].sort(sortFn);
      const sortedMids = [...mids].sort(sortFn);
      const sortedFwds = [...fwds].sort(sortFn);

      const startDefs = sortedDefs.slice(0, targetStructure.def);
      const startMids = sortedMids.slice(0, targetStructure.mid);
      const startFwds = sortedFwds.slice(0, targetStructure.fwd);

      startingXIList = [...startGkp, ...startDefs, ...startMids, ...startFwds];
      const startingIdsSet = new Set(startingXIList.map(getPlayerId));

      // Outfield bench is whatever outfield players remain
      const remainingOutfield = squad
        .filter((p) => normalizePosition(p.position) !== "GKP" && !startingIdsSet.has(getPlayerId(p)))
        .sort(sortFn);

      benchList = [...benchGkp, ...remainingOutfield];
    }

    const startDefsList = startingXIList.filter((p) => normalizePosition(p.position) === "DEF");
    const startMidsList = startingXIList.filter((p) => normalizePosition(p.position) === "MID");
    const startFwdsList = startingXIList.filter((p) => normalizePosition(p.position) === "FWD");

    const activeFormationStr = `${startDefsList.length}-${startMidsList.length}-${startFwdsList.length}`;

    // Resolve Captain & Vice Captain (must be in startingXI)
    let effectiveCaptain = startingXIList.find((p) => getPlayerId(p) === captainId) ?? null;
    let effectiveViceCaptain = startingXIList.find((p) => getPlayerId(p) === viceCaptainId) ?? null;

    if (!effectiveCaptain && startingXIList.length > 0) {
      effectiveCaptain = [...startingXIList].sort(sortFn)[0];
    }
    if (!effectiveViceCaptain && startingXIList.length > 1) {
      const remainingStarters = startingXIList.filter(
        (p) => getPlayerId(p) !== getPlayerId(effectiveCaptain!),
      );
      effectiveViceCaptain = [...remainingStarters].sort(sortFn)[0] ?? null;
    }

    // Points calculation (Whole integer display)
    const totalSquadXp = squad.reduce((sum, p) => sum + (p.predicted_total_points ?? 0), 0);

    let totalStartingXp = 0;
    for (const p of startingXIList) {
      const base = p.predicted_total_points ?? 0;
      if (effectiveCaptain && getPlayerId(p) === getPlayerId(effectiveCaptain)) {
        totalStartingXp += base * 2;
      } else {
        totalStartingXp += base;
      }
    }

    // Validation checks
    const errors: string[] = [];
    if (squad.length < SQUAD_SIZE) {
      errors.push(`Squad incomplete (${squad.length}/${SQUAD_SIZE} players).`);
    }
    if (startingXIList.length < 11) {
      errors.push(`Starting XI incomplete (${startingXIList.length}/11 players).`);
    }
    if (startDefsList.length < 3) {
      errors.push("Starting XI requires at least 3 Defenders.");
    }
    if (startMidsList.length < 2) {
      errors.push("Starting XI requires at least 2 Midfielders.");
    }
    if (startFwdsList.length < 1) {
      errors.push("Starting XI requires at least 1 Forward.");
    }
    if (totalSquadPrice > TOTAL_BUDGET + 0.001) {
      errors.push(`Squad exceeds £${TOTAL_BUDGET.toFixed(1)}m budget.`);
    }

    const isValid = errors.length === 0 && squad.length === SQUAD_SIZE;

    return {
      startingXI: startingXIList,
      bench: benchList,
      formationStr: activeFormationStr,
      effectiveCaptain,
      effectiveViceCaptain,
      totalStartingXp: Math.round(totalStartingXp),
      totalSquadXp: Math.round(totalSquadXp),
      isValidSquad: isValid,
      validationErrors: errors,
    };
  }, [squad, starterIds, formation, captainId, viceCaptainId, benchOrder, totalSquadPrice]);

  // Set explicit Captain
  const setCaptain = useCallback(
    (player: PlayerRecord) => {
      const pid = getPlayerId(player);
      const isStarter = startingXI.some((p) => getPlayerId(p) === pid);
      if (!isStarter) return;

      setCaptainId(pid);
      if (viceCaptainId === pid) {
        setViceCaptainId(null);
      }
    },
    [startingXI, viceCaptainId],
  );

  // Set explicit Vice-Captain
  const setViceCaptain = useCallback(
    (player: PlayerRecord) => {
      const pid = getPlayerId(player);
      const isStarter = startingXI.some((p) => getPlayerId(p) === pid);
      if (!isStarter) return;

      setViceCaptainId(pid);
      if (captainId === pid) {
        setCaptainId(null);
      }
    },
    [startingXI, captainId],
  );

  // Change formation with intelligent starter preservation & reallocation
  const setFormation = useCallback(
    (newFormation: Formation) => {
      setFormationState(newFormation);
      const target = parseFormation(newFormation);

      const sortFn = (a: PlayerRecord, b: PlayerRecord) =>
        (b.predicted_total_points ?? -100) - (a.predicted_total_points ?? -100);

      // Current starting players by position
      const curStarterSet = new Set(starterIds);
      const curGkps = squad.filter((p) => normalizePosition(p.position) === "GKP");
      const curDefs = squad.filter((p) => normalizePosition(p.position) === "DEF");
      const curMids = squad.filter((p) => normalizePosition(p.position) === "MID");
      const curFwds = squad.filter((p) => normalizePosition(p.position) === "FWD");

      const selectStartersForPos = (
        allPosPlayers: PlayerRecord[],
        targetCount: number,
      ): PlayerRecord[] => {
        if (allPosPlayers.length === 0) return [];
        const existingStarters = allPosPlayers.filter((p) => curStarterSet.has(getPlayerId(p)));
        const existingBench = allPosPlayers.filter((p) => !curStarterSet.has(getPlayerId(p)));

        if (existingStarters.length === targetCount) {
          return existingStarters;
        }

        if (existingStarters.length > targetCount) {
          // Excess starters: keep captains/VC first, then highest predicted points
          const sorted = [...existingStarters].sort((a, b) => {
            const aIsC = getPlayerId(a) === captainId ? 2 : getPlayerId(a) === viceCaptainId ? 1 : 0;
            const bIsC = getPlayerId(b) === captainId ? 2 : getPlayerId(b) === viceCaptainId ? 1 : 0;
            if (aIsC !== bIsC) return bIsC - aIsC;
            return sortFn(a, b);
          });
          return sorted.slice(0, targetCount);
        }

        // Need more starters: promote from bench
        const needed = targetCount - existingStarters.length;
        const sortedBench = [...existingBench].sort(sortFn);
        const promoted = sortedBench.slice(0, needed);
        return [...existingStarters, ...promoted];
      };

      const newStartGkps = selectStartersForPos(curGkps, 1);
      const newStartDefs = selectStartersForPos(curDefs, target.def);
      const newStartMids = selectStartersForPos(curMids, target.mid);
      const newStartFwds = selectStartersForPos(curFwds, target.fwd);

      const nextStarters = [
        ...newStartGkps,
        ...newStartDefs,
        ...newStartMids,
        ...newStartFwds,
      ];

      const nextStarterIds = nextStarters.map(getPlayerId);
      setStarterIds(nextStarterIds);

      // Safe Captaincy check: if Captain or VC is no longer in starting XI, safely handle
      if (captainId && !nextStarterIds.includes(captainId)) {
        // Transfer captaincy to top remaining starter
        const fallback = [...nextStarters].sort(sortFn)[0];
        setCaptainId(fallback ? getPlayerId(fallback) : null);
      }
      if (viceCaptainId && !nextStarterIds.includes(viceCaptainId)) {
        const remaining = nextStarters.filter((p) => getPlayerId(p) !== captainId);
        const fallbackVC = [...remaining].sort(sortFn)[0];
        setViceCaptainId(fallbackVC ? getPlayerId(fallbackVC) : null);
      }
    },
    [squad, starterIds, captainId, viceCaptainId],
  );

  // Reorder bench priority for outfield substitutes
  const reorderBench = useCallback((fromIndex: number, toIndex: number) => {
    setBenchOrder((currentOrder) => {
      const newOrder = [...currentOrder];
      if (fromIndex < 0 || fromIndex >= newOrder.length || toIndex < 0 || toIndex >= newOrder.length) {
        return currentOrder;
      }
      const [moved] = newOrder.splice(fromIndex, 1);
      newOrder.splice(toIndex, 0, moved);
      return newOrder;
    });
  }, []);

  // Auto Pick AI Squad Optimizer
  const autoPick = useCallback(
    (availablePlayers: PlayerRecord[]) => {
      if (!availablePlayers || availablePlayers.length === 0) return;

      const valid = availablePlayers.filter((p) => getPlayerPrice(p) > 0);
      const sortedByPoints = [...valid].sort(
        (a, b) => (b.predicted_total_points ?? -100) - (a.predicted_total_points ?? -100),
      );

      const gkps = sortedByPoints.filter((p) => normalizePosition(p.position) === "GKP");
      const defs = sortedByPoints.filter((p) => normalizePosition(p.position) === "DEF");
      const mids = sortedByPoints.filter((p) => normalizePosition(p.position) === "MID");
      const fwds = sortedByPoints.filter((p) => normalizePosition(p.position) === "FWD");

      const selected: PlayerRecord[] = [];
      const clubCounts: Record<string, number> = {};

      const tryAdd = (p: PlayerRecord): boolean => {
        const pid = getPlayerId(p);
        if (selected.some((s) => getPlayerId(s) === pid)) return false;

        const team = p.team;
        if (team && (clubCounts[team] || 0) >= 3) return false;

        const currentCost = selected.reduce((sum, s) => sum + getPlayerPrice(s), 0);
        if (currentCost + getPlayerPrice(p) > TOTAL_BUDGET + 0.001) return false;

        selected.push(p);
        if (team) clubCounts[team] = (clubCounts[team] || 0) + 1;
        return true;
      };

      const pickGroup = (group: PlayerRecord[], count: number) => {
        let added = 0;
        for (const p of group) {
          if (added >= count) break;
          if (tryAdd(p)) {
            added++;
          }
        }
      };

      pickGroup(gkps, 2);
      pickGroup(defs, 5);
      pickGroup(mids, 5);
      pickGroup(fwds, 3);

      if (selected.length < SQUAD_SIZE) {
        const cheapSort = (a: PlayerRecord, b: PlayerRecord) => getPlayerPrice(a) - getPlayerPrice(b);
        const needGkp = 2 - selected.filter((p) => normalizePosition(p.position) === "GKP").length;
        const needDef = 5 - selected.filter((p) => normalizePosition(p.position) === "DEF").length;
        const needMid = 5 - selected.filter((p) => normalizePosition(p.position) === "MID").length;
        const needFwd = 3 - selected.filter((p) => normalizePosition(p.position) === "FWD").length;

        if (needGkp > 0) pickGroup([...gkps].sort(cheapSort), 2);
        if (needDef > 0) pickGroup([...defs].sort(cheapSort), 5);
        if (needMid > 0) pickGroup([...mids].sort(cheapSort), 5);
        if (needFwd > 0) pickGroup([...fwds].sort(cheapSort), 3);
      }

      setSquad(selected);

      // Top starters based on formation
      const target = parseFormation(formation);
      const sortFn = (a: PlayerRecord, b: PlayerRecord) =>
        (b.predicted_total_points ?? -100) - (a.predicted_total_points ?? -100);

      const selGkps = selected.filter((p) => normalizePosition(p.position) === "GKP").sort(sortFn);
      const selDefs = selected.filter((p) => normalizePosition(p.position) === "DEF").sort(sortFn);
      const selMids = selected.filter((p) => normalizePosition(p.position) === "MID").sort(sortFn);
      const selFwds = selected.filter((p) => normalizePosition(p.position) === "FWD").sort(sortFn);

      const starters = [
        ...selGkps.slice(0, 1),
        ...selDefs.slice(0, target.def),
        ...selMids.slice(0, target.mid),
        ...selFwds.slice(0, target.fwd),
      ];

      setStarterIds(starters.map(getPlayerId));

      // Auto set captain to top starter
      if (starters.length > 0) {
        const sortedStarters = [...starters].sort(sortFn);
        setCaptainId(getPlayerId(sortedStarters[0]));
        if (sortedStarters.length > 1) {
          setViceCaptainId(getPlayerId(sortedStarters[1]));
        }
      }
    },
    [formation],
  );

  const canSwapPlayers = useCallback(
    (playerA: PlayerRecord, playerB: PlayerRecord): { allowed: boolean; reason?: string } => {
      const pidA = getPlayerId(playerA);
      const pidB = getPlayerId(playerB);

      if (pidA === pidB) {
        return { allowed: false, reason: "Cannot swap a player with themselves." };
      }

      const isAInXI = startingXI.some((p) => getPlayerId(p) === pidA);
      const isBInXI = startingXI.some((p) => getPlayerId(p) === pidB);

      if (isAInXI === isBInXI) {
        // Both in starting XI or both on bench: always allowed
        return { allowed: true };
      }

      const starter = isAInXI ? playerA : playerB;
      const sub = isAInXI ? playerB : playerA;

      const starterPos = normalizePosition(starter.position);
      const subPos = normalizePosition(sub.position);

      if (starterPos === "GKP" || subPos === "GKP") {
        if (starterPos !== subPos) {
          return {
            allowed: false,
            reason: "Goalkeepers can only be swapped with another Goalkeeper.",
          };
        }
        return { allowed: true };
      }

      if (starterPos === subPos) {
        return { allowed: true };
      }

      const currentCounts = {
        DEF: startingXI.filter((p) => normalizePosition(p.position) === "DEF").length,
        MID: startingXI.filter((p) => normalizePosition(p.position) === "MID").length,
        FWD: startingXI.filter((p) => normalizePosition(p.position) === "FWD").length,
      };

      const newCounts = {
        ...currentCounts,
        [starterPos]: currentCounts[starterPos as keyof typeof currentCounts] - 1,
        [subPos]: currentCounts[subPos as keyof typeof currentCounts] + 1,
      };

      if (newCounts.DEF < POSITION_MIN_STARTERS.DEF) {
        return {
          allowed: false,
          reason: `Starting XI requires at least ${POSITION_MIN_STARTERS.DEF} Defenders.`,
        };
      }
      if (newCounts.DEF > POSITION_MAX_STARTERS.DEF) {
        return {
          allowed: false,
          reason: `Starting XI cannot have more than ${POSITION_MAX_STARTERS.DEF} Defenders.`,
        };
      }

      if (newCounts.MID < POSITION_MIN_STARTERS.MID) {
        return {
          allowed: false,
          reason: `Starting XI requires at least ${POSITION_MIN_STARTERS.MID} Midfielders.`,
        };
      }
      if (newCounts.MID > POSITION_MAX_STARTERS.MID) {
        return {
          allowed: false,
          reason: `Starting XI cannot have more than ${POSITION_MAX_STARTERS.MID} Midfielders.`,
        };
      }

      if (newCounts.FWD < POSITION_MIN_STARTERS.FWD) {
        return {
          allowed: false,
          reason: `Starting XI requires at least ${POSITION_MIN_STARTERS.FWD} Forwards.`,
        };
      }
      if (newCounts.FWD > POSITION_MAX_STARTERS.FWD) {
        return {
          allowed: false,
          reason: `Starting XI cannot have more than ${POSITION_MAX_STARTERS.FWD} Forwards.`,
        };
      }

      return { allowed: true };
    },
    [startingXI],
  );

  const swapPlayers = useCallback(
    (playerA: PlayerRecord, playerB: PlayerRecord): { success: boolean; reason?: string } => {
      const pidA = getPlayerId(playerA);
      const pidB = getPlayerId(playerB);

      const check = canSwapPlayers(playerA, playerB);
      if (!check.allowed) {
        return { success: false, reason: check.reason };
      }

      const currentStarterIds = startingXI.map(getPlayerId);
      const isAInXI = currentStarterIds.includes(pidA);
      const isBInXI = currentStarterIds.includes(pidB);

      let nextStarterIds: string[];
      if (isAInXI && !isBInXI) {
        // Starter A swapped with Bench B: B enters Starting XI, A moves to bench
        nextStarterIds = currentStarterIds.map((id) => (id === pidA ? pidB : id));
        // If Starter A was Captain, Captain role transfers to incoming Starter B
        if (captainId === pidA) setCaptainId(pidB);
        if (viceCaptainId === pidA) setViceCaptainId(pidB);

        // Update bench order: replace B with A
        setBenchOrder((order) => {
          const idx = order.indexOf(pidB);
          if (idx !== -1) {
            const next = [...order];
            next[idx] = pidA;
            return next;
          }
          return [...order.filter((id) => id !== pidB), pidA];
        });
      } else if (!isAInXI && isBInXI) {
        // Bench A swapped with Starter B: A enters Starting XI, B moves to bench
        nextStarterIds = currentStarterIds.map((id) => (id === pidB ? pidA : id));
        if (captainId === pidB) setCaptainId(pidA);
        if (viceCaptainId === pidB) setViceCaptainId(pidA);

        setBenchOrder((order) => {
          const idx = order.indexOf(pidA);
          if (idx !== -1) {
            const next = [...order];
            next[idx] = pidB;
            return next;
          }
          return [...order.filter((id) => id !== pidA), pidB];
        });
      } else if (!isAInXI && !isBInXI) {
        // Both are on the bench: swap their bench order priorities
        nextStarterIds = [...currentStarterIds];
        setBenchOrder((order) => {
          const idxA = order.indexOf(pidA);
          const idxB = order.indexOf(pidB);
          if (idxA !== -1 && idxB !== -1) {
            const next = [...order];
            next[idxA] = pidB;
            next[idxB] = pidA;
            return next;
          }
          return order;
        });
      } else {
        // Both in starting XI
        nextStarterIds = [...currentStarterIds];
      }

      setStarterIds(nextStarterIds);
      return { success: true };
    },
    [startingXI, canSwapPlayers, captainId, viceCaptainId],
  );

  const movePlayerToBench = useCallback(
    (player: PlayerRecord): { success: boolean; reason?: string } => {
      const pid = getPlayerId(player);
      const isStarter = startingXI.some((p) => getPlayerId(p) === pid);

      if (!isStarter) {
        return { success: false, reason: "Player is already on the bench." };
      }

      if (bench.length >= 4) {
        return {
          success: false,
          reason: "Bench is full. Please choose a substitute to swap with.",
        };
      }

      const pos = normalizePosition(player.position);
      const posStartersCount = startingXI.filter(
        (p) => normalizePosition(p.position) === pos,
      ).length;
      const minRequired = POSITION_MIN_STARTERS[pos] ?? 1;

      if (posStartersCount <= minRequired) {
        const posLabel =
          pos === "GKP"
            ? "Goalkeepers"
            : pos === "DEF"
              ? "Defenders"
              : pos === "MID"
                ? "Midfielders"
                : "Forwards";
        return {
          success: false,
          reason: `Starting XI requires at least ${minRequired} ${posLabel}.`,
        };
      }

      const currentStarterIds = startingXI.map(getPlayerId);
      setStarterIds(currentStarterIds.filter((id) => id !== pid));
      if (captainId === pid) setCaptainId(null);
      if (viceCaptainId === pid) setViceCaptainId(null);
      return { success: true };
    },
    [startingXI, bench, captainId, viceCaptainId],
  );

  const movePlayerToStartingXI = useCallback(
    (player: PlayerRecord): { success: boolean; reason?: string } => {
      const pid = getPlayerId(player);
      const isStarter = startingXI.some((p) => getPlayerId(p) === pid);

      if (isStarter) {
        return { success: false, reason: "Player is already in Starting XI." };
      }

      if (startingXI.length >= 11) {
        return {
          success: false,
          reason: "Starting XI is full (11/11). Choose a starting player to swap with.",
        };
      }

      const pos = normalizePosition(player.position);
      const posStartersCount = startingXI.filter(
        (p) => normalizePosition(p.position) === pos,
      ).length;
      const maxAllowed = POSITION_MAX_STARTERS[pos] ?? 5;

      if (posStartersCount >= maxAllowed) {
        const posLabel =
          pos === "GKP"
            ? "Goalkeepers"
            : pos === "DEF"
              ? "Defenders"
              : pos === "MID"
                ? "Midfielders"
                : "Forwards";
        return {
          success: false,
          reason: `Starting XI cannot have more than ${maxAllowed} ${posLabel}.`,
        };
      }

      const currentStarterIds = startingXI.map(getPlayerId);
      setStarterIds([...currentStarterIds, pid]);
      return { success: true };
    },
    [startingXI],
  );

  return {
    squad,
    startingXI,
    bench,
    formation,
    formationStr,
    captainId,
    viceCaptainId,
    effectiveCaptain,
    effectiveViceCaptain,
    benchOrder,
    setCaptain,
    setViceCaptain,
    setFormation,
    reorderBench,
    isFull: squad.length >= SQUAD_SIZE,
    maxSize: SQUAD_SIZE,
    totalSquadPrice,
    remainingBudget,
    totalStartingXp,
    totalSquadXp,
    isValidSquad,
    validationErrors,
    isInSquad,
    canAddPlayer,
    canReplacePlayer,
    addPlayer,
    removePlayer,
    replacePlayer,
    togglePlayer,
    resetSquad,
    autoPick,
    getPositionCounts,
    getClubCounts,
    canSwapPlayers,
    swapPlayers,
    movePlayerToBench,
    movePlayerToStartingXI,
  };
}
