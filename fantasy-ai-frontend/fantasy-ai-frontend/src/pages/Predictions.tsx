import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, Shield, Sparkles } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import { PlayerCard } from "@/components/PlayerCard";
import { FilterBar } from "@/components/FilterBar";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";
import { formatStat } from "@/lib/format";

const SORT_OPTIONS = [
  { value: "predicted_total_points", label: "Predicted Points" },
  { value: "total_points_avg_last_3", label: "Form (3gw)" },
  { value: "value", label: "Price" },
  { value: "minutes_avg_last_5", label: "Minutes" },
  { value: "name", label: "Name" },
];

export default function Predictions() {
  const { data, loading, error, refetch } = usePredictions();
  const [query, setQuery] = useState("");
  const [team, setTeam] = useState("all");
  const [position, setPosition] = useState("all");
  const [sortKey, setSortKey] = useState("predicted_total_points");
  const [selected, setSelected] = useState<PlayerRecord | null>(null);

  const predictions = data?.predictions ?? [];
  const gameweek = predictions[0]?.predicted_for_gw;

  const filtered = useMemo(() => {
    return predictions
      .filter((p) => (team === "all" ? true : p.team === team))
      .filter((p) => (position === "all" ? true : p.position === position))
      .filter((p) => {
        if (!query.trim()) return true;
        const q = query.toLowerCase();
        return (
          p.name?.toLowerCase().includes(q) ||
          p.team?.toLowerCase().includes(q) ||
          p.position?.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => {
        const key = sortKey as keyof PlayerRecord;
        const av = a[key];
        const bv = b[key];
        if (typeof av === "string" || typeof bv === "string") {
          return String(av ?? "").localeCompare(String(bv ?? ""));
        }
        const an = typeof av === "number" ? av : -Infinity;
        const bn = typeof bv === "number" ? bv : -Infinity;
        return bn - an;
      });
  }, [predictions, query, team, position, sortKey]);

  // Derive summary stats from real data
  const summaryStats = useMemo(() => {
    if (predictions.length === 0) return null;
    const topPlayer = predictions.reduce<PlayerRecord | null>((best, p) => {
      if (!best) return p;
      return (p.predicted_total_points ?? -1) > (best.predicted_total_points ?? -1) ? p : best;
    }, null);
    const favorableFixtures = predictions.filter(
      (p) => typeof p.fixture_difficulty === "number" && p.fixture_difficulty <= 2,
    ).length;
    const inForm = predictions.filter(
      (p) =>
        typeof p.total_points_avg_last_3 === "number" &&
        typeof p.total_points_avg_last_10 === "number" &&
        p.total_points_avg_last_3 > p.total_points_avg_last_10,
    ).length;

    return { topPlayer, favorableFixtures, inForm };
  }, [predictions]);

  return (
    <div className="mx-auto max-w-7xl px-5 py-6 pb-safe-bottom lg:px-8">
      {/* Page header */}
      <div className="mb-6 flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald/10 text-emerald">
            <BarChart3 size={18} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-bold text-ink sm:text-3xl">
              AI Predictions
              {typeof gameweek === "number" && (
                <span className="ml-2 text-emerald">GW {gameweek}</span>
              )}
            </h1>
          </div>
        </div>
        <p className="mt-1 text-sm text-ink-tertiary">
          {data ? data.predicted_for_gw_note : "AI-projected points for every tracked player."}
        </p>
      </div>

      {/* Summary strip — derived from real data only */}
      {!loading && !error && summaryStats && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3"
        >
          {summaryStats.topPlayer && (
            <div className="flex items-center gap-3 rounded-xl border border-gold/15 bg-gold/[0.04] px-4 py-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gold/15 text-gold">
                <Sparkles size={15} />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] font-medium uppercase tracking-wider text-ink-tertiary">
                  Top Prediction
                </div>
                <div className="truncate text-sm font-semibold text-ink">
                  {summaryStats.topPlayer.name ?? "N/A"}{" "}
                  <span className="numeral text-gold">
                    {formatStat(summaryStats.topPlayer.predicted_total_points)}
                  </span>
                </div>
              </div>
            </div>
          )}
          {summaryStats.favorableFixtures > 0 && (
            <div className="flex items-center gap-3 rounded-xl border border-emerald/15 bg-emerald/[0.04] px-4 py-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald/15 text-emerald">
                <Shield size={15} />
              </div>
              <div>
                <div className="text-[10px] font-medium uppercase tracking-wider text-ink-tertiary">
                  Favorable Fixtures
                </div>
                <div className="text-sm font-semibold text-ink">
                  {summaryStats.favorableFixtures} players
                </div>
              </div>
            </div>
          )}
          {summaryStats.inForm > 0 && (
            <div className="flex items-center gap-3 rounded-xl border border-signal/15 bg-signal/[0.04] px-4 py-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-signal/15 text-signal">
                <TrendingUp size={15} />
              </div>
              <div>
                <div className="text-[10px] font-medium uppercase tracking-wider text-ink-tertiary">
                  Players In Form
                </div>
                <div className="text-sm font-semibold text-ink">
                  {summaryStats.inForm} improving
                </div>
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* Filter bar */}
      <div className="mb-6">
        <FilterBar
          predictions={predictions}
          query={query}
          onQueryChange={setQuery}
          team={team}
          onTeamChange={setTeam}
          position={position}
          onPositionChange={setPosition}
          sortKey={sortKey}
          onSortChange={setSortKey}
          sortOptions={SORT_OPTIONS}
        />
      </div>

      {/* Results count */}
      {!loading && !error && filtered.length > 0 && (
        <div className="mb-4 text-xs text-ink-tertiary">
          Showing {filtered.length} of {predictions.length} players
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 9 }).map((_, i) => (
            <PlayerCardSkeleton key={i} />
          ))}
        </div>
      )}

      {!loading && error && <ErrorState message={error} onRetry={refetch} />}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title="No players match your filters"
          description="Try a different search term or clear the filters."
        />
      )}

      {/* Player grid */}
      {!loading && !error && filtered.length > 0 && (
        <motion.div layout className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p, i) => (
            <PlayerCard
              key={p.element ?? p.name}
              player={p}
              rank={i + 1}
              onClick={() => setSelected(p)}
            />
          ))}
        </motion.div>
      )}

      {/* Player detail drawer */}
      <Drawer open={selected !== null} onClose={() => setSelected(null)}>
        {selected && <PlayerDetailPanel player={selected} />}
      </Drawer>
    </div>
  );
}
