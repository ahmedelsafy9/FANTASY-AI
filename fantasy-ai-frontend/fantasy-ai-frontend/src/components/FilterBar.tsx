import { useMemo } from "react";
import type { PlayerRecord } from "@/types/api";
import { SearchInput } from "@/components/ui/SearchInput";
import { Dropdown } from "@/components/ui/overlays";
import { cn } from "@/lib/utils";

interface FilterBarProps {
  predictions: PlayerRecord[];
  query: string;
  onQueryChange: (v: string) => void;
  team: string;
  onTeamChange: (v: string) => void;
  position: string;
  onPositionChange: (v: string) => void;
  sortKey: string;
  onSortChange: (v: string) => void;
  sortOptions: { value: string; label: string }[];
  className?: string;
}

/**
 * Consolidated filter/sort bar used on Predictions and Players pages.
 * Dynamically derives team and position options from the prediction data.
 */
export function FilterBar({
  predictions,
  query,
  onQueryChange,
  team,
  onTeamChange,
  position,
  onPositionChange,
  sortKey,
  onSortChange,
  sortOptions,
  className,
}: FilterBarProps) {
  const teamOptions = useMemo(() => {
    const unique = Array.from(new Set(predictions.map((p) => p.team).filter(Boolean))) as string[];
    return [{ value: "all", label: "All Teams" }, ...unique.sort().map((t) => ({ value: t, label: t }))];
  }, [predictions]);

  const positionOptions = useMemo(() => {
    const unique = Array.from(
      new Set(predictions.map((p) => p.position).filter(Boolean)),
    ) as string[];
    const order = ["GKP", "DEF", "MID", "FWD", "GK"];
    const sorted = unique.sort((a, b) => {
      const ai = order.indexOf(a);
      const bi = order.indexOf(b);
      return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
    });
    return [
      { value: "all", label: "All Positions" },
      ...sorted.map((p) => ({ value: p, label: p === "GKP" ? "GK" : p })),
    ];
  }, [predictions]);

  return (
    <div className={cn("flex flex-col gap-3 sm:flex-row sm:items-center", className)}>
      <div className="flex-1 min-w-0 max-w-md">
        <SearchInput value={query} onChange={onQueryChange} />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Dropdown label="Team" options={teamOptions} value={team} onChange={onTeamChange} />
        <Dropdown label="Position" options={positionOptions} value={position} onChange={onPositionChange} />
        <Dropdown label="Sort" options={sortOptions} value={sortKey} onChange={onSortChange} />
      </div>
    </div>
  );
}
