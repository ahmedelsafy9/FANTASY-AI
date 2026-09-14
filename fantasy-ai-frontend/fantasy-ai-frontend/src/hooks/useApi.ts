import { useCallback } from "react";
import { useAsync } from "./useAsync";
import {
  getCaptain,
  getDifferentials,
  getHealth,
  getMatchPredictions,
  getPlayer,
  getPredictions,
  getTopPlayers,
  DifferentialQueryParams,
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

export function useMatchPredictions() {
  return useAsync(useCallback(() => getMatchPredictions(), []));
}

export function useDifferentials(params?: DifferentialQueryParams) {
  return useAsync(
    useCallback(() => getDifferentials(params), [params?.limit, params?.category, params?.position, params?.max_price, params?.max_ownership]),
    [params?.limit, params?.category, params?.position, params?.max_price, params?.max_ownership],
  );
}
