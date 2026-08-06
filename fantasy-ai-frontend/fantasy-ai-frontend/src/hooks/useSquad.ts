import { useCallback, useMemo, useState } from "react";
import type { PlayerRecord } from "@/types/api";

const SQUAD_SIZE = 15;

/**
 * Phase 7: a lightweight squad-building experience built entirely from
 * existing prediction data — no backend changes required. Squad state is
 * kept client-side (session only); this is deliberately NOT persisted to
 * a fake backend endpoint that doesn't exist, avoiding invented data.
 */
export function useSquad() {
  const [squad, setSquad] = useState<PlayerRecord[]>([]);

  const isInSquad = useCallback(
    (player: PlayerRecord) => squad.some((p) => (p.element ?? p.name) === (player.element ?? player.name)),
    [squad],
  );

  const addPlayer = useCallback((player: PlayerRecord) => {
    setSquad((current) => {
      if (current.length >= SQUAD_SIZE) return current;
      if (current.some((p) => (p.element ?? p.name) === (player.element ?? player.name))) return current;
      return [...current, player];
    });
  }, []);

  const removePlayer = useCallback((player: PlayerRecord) => {
    setSquad((current) =>
      current.filter((p) => (p.element ?? p.name) !== (player.element ?? player.name)),
    );
  }, []);

  const toggle = useCallback(
    (player: PlayerRecord) => {
      if (isInSquad(player)) removePlayer(player);
      else addPlayer(player);
    },
    [isInSquad, addPlayer, removePlayer],
  );

  const totalExpectedPoints = useMemo(
    () => squad.reduce((sum, p) => sum + (p.predicted_total_points ?? 0), 0),
    [squad],
  );

  const totalPrice = useMemo(
    () => squad.reduce((sum, p) => sum + (p.value ?? 0), 0),
    [squad],
  );

  const bestXI = useMemo(
    () =>
      [...squad]
        .sort((a, b) => (b.predicted_total_points ?? -Infinity) - (a.predicted_total_points ?? -Infinity))
        .slice(0, 11),
    [squad],
  );

  return {
    squad,
    isFull: squad.length >= SQUAD_SIZE,
    maxSize: SQUAD_SIZE,
    isInSquad,
    addPlayer,
    removePlayer,
    toggle,
    totalExpectedPoints,
    totalPrice,
    bestXI,
  };
}
