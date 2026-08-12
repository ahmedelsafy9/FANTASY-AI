import { useCallback, useMemo, useState } from "react";
import type { PlayerRecord } from "@/types/api";

const SQUAD_SIZE = 15;
export const TOTAL_BUDGET = 100.0; // £100.0m

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

export function useSquad() {
  const [squad, setSquad] = useState<PlayerRecord[]>([]);
  const [starterIds, setStarterIds] = useState<string[]>([]);
  const [captainId, setCaptainId] = useState<string | null>(null);
  const [viceCaptainId, setViceCaptainId] = useState<string | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  const [_benchOrder, _setBenchOrder] = useState<string[]>([]);

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
    (player: PlayerRecord): AddPlayerResult => {
      const pid = getPlayerId(player);
      if (squad.some((p) => getPlayerId(p) === pid)) {
        return { allowed: false, reason: "Already in squad" };
      }
      if (squad.length >= SQUAD_SIZE) {
        return { allowed: false, reason: "Squad is full (15/15)" };
      }

      const price = getPlayerPrice(player);
      if (price > remainingBudget + 0.001) {
        return {
          allowed: false,
          reason: `Not enough budget (Requires £${price.toFixed(1)}m, Remaining £${remainingBudget.toFixed(1)}m)`,
        };
      }

      const pos = normalizePosition(player.position);
      const posCounts = getPositionCounts(squad);
      const posLimit = POSITION_LIMITS[pos] ?? 5;
      if ((posCounts[pos] || 0) >= posLimit) {
        const label = pos === "GKP" ? "Goalkeepers" : pos === "DEF" ? "Defenders" : pos === "MID" ? "Midfielders" : "Forwards";
        return { allowed: false, reason: `You already have ${posLimit} ${label}` };
      }

      if (player.team) {
        const clubCounts = getClubCounts(squad);
        if ((clubCounts[player.team] || 0) >= 3) {
          return { allowed: false, reason: `Maximum 3 players allowed from ${player.team}` };
        }
      }

      return { allowed: true };
    },
    [squad, remainingBudget, getPositionCounts, getClubCounts],
  );

  const addPlayer = useCallback(
    (player: PlayerRecord): boolean => {
      const check = canAddPlayer(player);
      if (!check.allowed) return false;
      setSquad((current) => [...current, player]);
      return true;
    },
    [canAddPlayer],
  );

  const removePlayer = useCallback((player: PlayerRecord) => {
    const pid = getPlayerId(player);
    setSquad((current) => current.filter((p) => getPlayerId(p) !== pid));
    setStarterIds((ids) => ids.filter((id) => id !== pid));
    setCaptainId((cid) => (cid === pid ? null : cid));
    setViceCaptainId((vcid) => (vcid === pid ? null : vcid));
  }, []);

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
    _setBenchOrder([]);
  }, []);

  // Compute Starting XI, Bench, Formation, Captains, and Totals
  const {
    startingXI,
    bench,
    formationStr,
    effectiveCaptain,
    effectiveViceCaptain,
    totalStartingXp,
    totalSquadXp,
  } = useMemo(() => {
    if (squad.length === 0) {
      return {
        startingXI: [],
        bench: [],
        formationStr: "0-0-0",
        effectiveCaptain: null,
        effectiveViceCaptain: null,
        totalStartingXp: 0,
        totalSquadXp: 0,
      };
    }

    const sortFn = (a: PlayerRecord, b: PlayerRecord) =>
      (b.predicted_total_points ?? -100) - (a.predicted_total_points ?? -100);

    const validStarterIds = starterIds.filter((id) =>
      squad.some((p) => getPlayerId(p) === id)
    );

    let startingXIList: PlayerRecord[] = [];
    let benchList: PlayerRecord[] = [];

    if (validStarterIds.length > 0) {
      startingXIList = squad.filter((p) => validStarterIds.includes(getPlayerId(p)));
      benchList = squad.filter((p) => !validStarterIds.includes(getPlayerId(p)));
    } else {
      const gkps = squad.filter((p) => normalizePosition(p.position) === "GKP");
      const defs = squad.filter((p) => normalizePosition(p.position) === "DEF");
      const mids = squad.filter((p) => normalizePosition(p.position) === "MID");
      const fwds = squad.filter((p) => normalizePosition(p.position) === "FWD");

      const sortedGkps = [...gkps].sort(sortFn);
      const startGkp = sortedGkps.slice(0, 1);
      const benchGkp = sortedGkps.slice(1);

      const sortedDefs = [...defs].sort(sortFn);
      const sortedMids = [...mids].sort(sortFn);
      const sortedFwds = [...fwds].sort(sortFn);

      const minDef = Math.min(sortedDefs.length, POSITION_MIN_STARTERS.DEF);
      const minMid = Math.min(sortedMids.length, POSITION_MIN_STARTERS.MID);
      const minFwd = Math.min(sortedFwds.length, POSITION_MIN_STARTERS.FWD);

      let startDefs = sortedDefs.slice(0, minDef);
      let startMids = sortedMids.slice(0, minMid);
      let startFwds = sortedFwds.slice(0, minFwd);

      let availDefs = sortedDefs.slice(minDef);
      let availMids = sortedMids.slice(minMid);
      let availFwds = sortedFwds.slice(minFwd);

      const neededOutfield = 10 - (startDefs.length + startMids.length + startFwds.length);

      const pool: { player: PlayerRecord; pos: string }[] = [
        ...availDefs.map((p) => ({ player: p, pos: "DEF" })),
        ...availMids.map((p) => ({ player: p, pos: "MID" })),
        ...availFwds.map((p) => ({ player: p, pos: "FWD" })),
      ].sort((a, b) => sortFn(a.player, b.player));

      let addedCount = 0;
      for (const item of pool) {
        if (addedCount >= neededOutfield) break;
        if (item.pos === "DEF" && startDefs.length < POSITION_MAX_STARTERS.DEF) {
          startDefs.push(item.player);
          addedCount++;
        } else if (item.pos === "MID" && startMids.length < POSITION_MAX_STARTERS.MID) {
          startMids.push(item.player);
          addedCount++;
        } else if (item.pos === "FWD" && startFwds.length < POSITION_MAX_STARTERS.FWD) {
          startFwds.push(item.player);
          addedCount++;
        }
      }

      startingXIList = [...startGkp, ...startDefs, ...startMids, ...startFwds];
      const startingIdsSet = new Set(startingXIList.map(getPlayerId));

      const remainingOutfield = squad
        .filter((p) => normalizePosition(p.position) !== "GKP" && !startingIdsSet.has(getPlayerId(p)))
        .sort(sortFn);

      benchList = [...benchGkp, ...remainingOutfield];
    }

    const startDefsList = startingXIList.filter((p) => normalizePosition(p.position) === "DEF");
    const startMidsList = startingXIList.filter((p) => normalizePosition(p.position) === "MID");
    const startFwdsList = startingXIList.filter((p) => normalizePosition(p.position) === "FWD");

    const formationStr = `${startDefsList.length}-${startMidsList.length}-${startFwdsList.length}`;

    // Resolve Captain & Vice Captain
    let effectiveCaptain = startingXIList.find((p) => getPlayerId(p) === captainId) ?? null;
    let effectiveViceCaptain = startingXIList.find((p) => getPlayerId(p) === viceCaptainId) ?? null;

    if (!effectiveCaptain && startingXIList.length > 0) {
      effectiveCaptain = [...startingXIList].sort(sortFn)[0];
    }
    if (!effectiveViceCaptain && startingXIList.length > 1) {
      const remainingStarters = startingXIList.filter((p) => getPlayerId(p) !== getPlayerId(effectiveCaptain!));
      effectiveViceCaptain = [...remainingStarters].sort(sortFn)[0] ?? null;
    }

    // Points calculation
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

    return {
      startingXI: startingXIList,
      bench: benchList,
      formationStr,
      effectiveCaptain,
      effectiveViceCaptain,
      totalStartingXp,
      totalSquadXp,
    };
  }, [squad, starterIds, captainId, viceCaptainId]);

  // Auto Pick AI Squad Optimizer
  const autoPick = useCallback((availablePlayers: PlayerRecord[]) => {
    if (!availablePlayers || availablePlayers.length === 0) return;

    // Filter valid players with positive prediction/price
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

    // Pick top required count for each position
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

    // If budget was exceeded or group missing, fill remaining with cheapest valid
    if (selected.length < SQUAD_SIZE) {
      const needGkp = 2 - selected.filter((p) => normalizePosition(p.position) === "GKP").length;
      const needDef = 5 - selected.filter((p) => normalizePosition(p.position) === "DEF").length;
      const needMid = 5 - selected.filter((p) => normalizePosition(p.position) === "MID").length;
      const needFwd = 3 - selected.filter((p) => normalizePosition(p.position) === "FWD").length;

      const cheapSort = (a: PlayerRecord, b: PlayerRecord) => getPlayerPrice(a) - getPlayerPrice(b);
      if (needGkp > 0) pickGroup([...gkps].sort(cheapSort), 2);
      if (needDef > 0) pickGroup([...defs].sort(cheapSort), 5);
      if (needMid > 0) pickGroup([...mids].sort(cheapSort), 5);
      if (needFwd > 0) pickGroup([...fwds].sort(cheapSort), 3);
    }

    setSquad(selected);

    // Auto set captain to top scorer
    if (selected.length > 0) {
      const topScorer = [...selected].sort(
        (a, b) => (b.predicted_total_points ?? -100) - (a.predicted_total_points ?? -100),
      )[0];
      setCaptainId(getPlayerId(topScorer));

      const secondScorer = [...selected].sort(
        (a, b) => (b.predicted_total_points ?? -100) - (a.predicted_total_points ?? -100),
      )[1];
      if (secondScorer) {
        setViceCaptainId(getPlayerId(secondScorer));
      }
    }
    setStarterIds([]);
  }, []);

  const canSwapPlayers = useCallback(
    (playerA: PlayerRecord, playerB: PlayerRecord): { allowed: boolean; reason?: string } => {
      const pidA = getPlayerId(playerA);
      const pidB = getPlayerId(playerB);

      if (pidA === pidB) {
        return { allowed: false, reason: "Cannot swap a player with themselves" };
      }

      const isAInXI = startingXI.some((p) => getPlayerId(p) === pidA);
      const isBInXI = startingXI.some((p) => getPlayerId(p) === pidB);

      if (isAInXI === isBInXI) {
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
          reason: `Cannot swap: Starting XI requires at least ${POSITION_MIN_STARTERS.DEF} Defenders.`,
        };
      }
      if (newCounts.DEF > POSITION_MAX_STARTERS.DEF) {
        return {
          allowed: false,
          reason: `Cannot swap: Starting XI cannot have more than ${POSITION_MAX_STARTERS.DEF} Defenders.`,
        };
      }

      if (newCounts.MID < POSITION_MIN_STARTERS.MID) {
        return {
          allowed: false,
          reason: `Cannot swap: Starting XI requires at least ${POSITION_MIN_STARTERS.MID} Midfielders.`,
        };
      }
      if (newCounts.MID > POSITION_MAX_STARTERS.MID) {
        return {
          allowed: false,
          reason: `Cannot swap: Starting XI cannot have more than ${POSITION_MAX_STARTERS.MID} Midfielders.`,
        };
      }

      if (newCounts.FWD < POSITION_MIN_STARTERS.FWD) {
        return {
          allowed: false,
          reason: `Cannot swap: Starting XI requires at least ${POSITION_MIN_STARTERS.FWD} Forwards.`,
        };
      }
      if (newCounts.FWD > POSITION_MAX_STARTERS.FWD) {
        return {
          allowed: false,
          reason: `Cannot swap: Starting XI cannot have more than ${POSITION_MAX_STARTERS.FWD} Forwards.`,
        };
      }

      return { allowed: true };
    },
    [startingXI]
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
        nextStarterIds = currentStarterIds.map((id) => (id === pidA ? pidB : id));
      } else if (!isAInXI && isBInXI) {
        nextStarterIds = currentStarterIds.map((id) => (id === pidB ? pidA : id));
      } else {
        nextStarterIds = [...currentStarterIds];
      }

      setStarterIds(nextStarterIds);
      return { success: true };
    },
    [startingXI, canSwapPlayers]
  );

  const movePlayerToBench = useCallback(
    (player: PlayerRecord): { success: boolean; reason?: string } => {
      const pid = getPlayerId(player);
      const isStarter = startingXI.some((p) => getPlayerId(p) === pid);

      if (!isStarter) {
        return { success: false, reason: "Player is already on the bench" };
      }

      if (bench.length >= 4) {
        return {
          success: false,
          reason: "Bench is full — choose a substitute to swap.",
        };
      }

      const pos = normalizePosition(player.position);
      const posStartersCount = startingXI.filter(
        (p) => normalizePosition(p.position) === pos
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
          reason: `Cannot move to bench: Starting XI requires at least ${minRequired} ${posLabel}.`,
        };
      }

      const currentStarterIds = startingXI.map(getPlayerId);
      setStarterIds(currentStarterIds.filter((id) => id !== pid));
      return { success: true };
    },
    [startingXI, bench]
  );

  const movePlayerToStartingXI = useCallback(
    (player: PlayerRecord): { success: boolean; reason?: string } => {
      const pid = getPlayerId(player);
      const isStarter = startingXI.some((p) => getPlayerId(p) === pid);

      if (isStarter) {
        return { success: false, reason: "Player is already in Starting XI" };
      }

      if (startingXI.length >= 11) {
        return {
          success: false,
          reason: "Starting XI is full (11/11). Choose a starting player to swap.",
        };
      }

      const pos = normalizePosition(player.position);
      const posStartersCount = startingXI.filter(
        (p) => normalizePosition(p.position) === pos
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
          reason: `Cannot move to XI: Starting XI cannot have more than ${maxAllowed} ${posLabel}.`,
        };
      }

      const currentStarterIds = startingXI.map(getPlayerId);
      setStarterIds([...currentStarterIds, pid]);
      return { success: true };
    },
    [startingXI]
  );

  return {
    squad,
    startingXI,
    bench,
    formationStr,
    captainId,
    viceCaptainId,
    effectiveCaptain,
    effectiveViceCaptain,
    setCaptainId,
    setViceCaptainId,
    isFull: squad.length >= SQUAD_SIZE,
    maxSize: SQUAD_SIZE,
    totalSquadPrice,
    remainingBudget,
    totalStartingXp,
    totalSquadXp,
    isInSquad,
    canAddPlayer,
    addPlayer,
    removePlayer,
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
