import { useCallback } from "react";
import { useAsync } from "./useAsync";
import {
  getCaptain,
  getHealth,
  getPlayer,
  getPredictions,
  getTopPlayers,
} from "@/api/endpoints";

export function useHealth() {
  return useAsync(useCallback(() => getHealth(), []));
}

export function usePlayer(playerId: string | undefined) {
  return useAsync(
    useCallback(() => {
      if (!playerId) return Promise.reject(new Error("No player selected."));
      return getPlayer(playerId);
    }, [playerId]),
    [playerId],
  );
}

export function usePredictions(playerId?: string) {
  return useAsync(useCallback(() => getPredictions(playerId), [playerId]), [playerId]);
}

export function useTopPlayers(limit = 10) {
  return useAsync(useCallback(() => getTopPlayers(limit), [limit]), [limit]);
}

export function useCaptain() {
  return useAsync(useCallback(() => getCaptain(), []));
}
