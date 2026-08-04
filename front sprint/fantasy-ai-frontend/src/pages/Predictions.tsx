import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import { PlayerCard } from "@/components/PlayerCard";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { SearchInput } from "@/components/ui/SearchInput";
import { Dropdown, Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";

export default function Predictions() {
  const { data, loading, error, refetch } = usePredictions();
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("all");
  const [selected, setSelected] = useState<PlayerRecord | null>(null);

  const predictions = data?.predictions ?? [];

  const teamOptions = useMemo(() => {
    const unique = Array.from(new Set(predictions.map((p) => p.team).filter(Boolean))) as string[];
    return [{ value: "all", label: "All teams" }, ...unique.sort().map((t) => ({ value: t, label: t }))];
  }, [predictions]);

  const filtered = useMemo(() => {
    return predictions
      .filter((p) => (team === "all" ? true : p.team === team))
      .filter((p) => {
        if (!query.trim()) return true;
        const q = query.toLowerCase();
        return (
          p.name?.toLowerCase().includes(q) ||
          p.team?.toLowerCase().includes(q) ||
          p.position?.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => (b.predicted_total_points ?? -Infinity) - (a.predicted_total_points ?? -Infinity));
  }, [predictions, query, team]);

  return (
    <div className="mx-auto max-w-7xl px-5 py-10 pb-24 lg:px-8">
      <div className="mb-8 flex flex-col gap-1">
        <h1 className="text-3xl font-semibold text-ink">Predictions</h1>
        <p className="text-sm text-ink-tertiary">
          {data ? data.predicted_for_gw_note : "AI-projected points for every tracked player."}
        </p>
      </div>

      <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex-1">
          <SearchInput value={query} onChange={setQuery} />
        </div>
        <Dropdown label="Team" options={teamOptions} value={team} onChange={setTeam} />
      </div>

      {loading && (
        <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <PlayerCardSkeleton key={i} />
          ))}
        </div>
      )}

      {!loading && error && <ErrorState message={error} onRetry={refetch} />}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title="No players match your filters"
          description="Try a different search term or clear the team filter."
        />
      )}

      {!loading && !error && filtered.length > 0 && (
        <motion.div
          layout
          className="grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3"
        >
          {filtered.map((p) => (
            <PlayerCard key={p.element ?? p.name} player={p} onClick={() => setSelected(p)} />
          ))}
        </motion.div>
      )}

      <Drawer open={selected !== null} onClose={() => setSelected(null)}>
        {selected && <PlayerDetailPanel player={selected} />}
      </Drawer>
    </div>
  );
}
