import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, Shield, Sparkles } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import { normalizePosition } from "@/hooks/useSquad";
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
      .filter((p) => {
        if (position === "all") return true;
        return normalizePosition(p.position) === normalizePosition(position);
      })
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
        if (sortKey === "value") {
          const av = a.value ?? a.now_cost ?? 0;
          const bv = b.value ?? b.now_cost ?? 0;
          return Number(bv) - Number(av);
        }
        if (sortKey === "name") {
          return String(a.name ?? "").localeCompare(String(b.name ?? ""));
        }
        const key = sortKey as keyof PlayerRecord;
        const av = a[key];
        const bv = b[key];
        const an = typeof av === "number" ? av : -Infinity;
        const bn = typeof bv === "number" ? bv : -Infinity;
        return bn - an;
      });
  }, [predictions, query, team, position, sortKey]);

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
    <div className="mx-auto max-w-7xl px-4 py-6 pb-safe-bottom sm:px-6 lg:px-8">
      {/* Page header */}
      <div className="mb-6 flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] shadow-sm">
            <BarChart3 size={20} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-[#0F172A] sm:text-3xl">
              AI Points Predictions
              {typeof gameweek === "number" && (
                <span className="ml-2.5 text-[#10B981] font-black">GW {gameweek}</span>
              )}
            </h1>
          </div>
        </div>
        <p className="mt-1 text-sm font-semibold text-[#475569]">
          {data ? data.predicted_for_gw_note : "AI-projected points for every tracked player."}
        </p>
      </div>

      {/* Summary strip */}
      {!loading && !error && summaryStats && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3"
        >
          {summaryStats.topPlayer && (
            <div className="flex items-center gap-3.5 rounded-chunky-lg border border-[#FDE68A] bg-[#FFFBEB] px-4 py-3.5 shadow-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#F59E0B] text-[#0F172A] shadow-sm">
                <Sparkles size={18} />
              </div>
              <div className="min-w-0">
                <div className="text-[10px] font-black uppercase text-[#92400E]">
                  Top AI Prediction
                </div>
                <div className="truncate text-sm font-black text-[#0F172A]">
                  {summaryStats.topPlayer.name ?? "N/A"}{" "}
                  <span className="numeral text-[#92400E] font-black">
                    {formatStat(summaryStats.topPlayer.predicted_total_points)} xPts
                  </span>
                </div>
              </div>
            </div>
          )}
          {summaryStats.favorableFixtures > 0 && (
            <div className="flex items-center gap-3.5 rounded-chunky-lg border border-[#A7F3D0] bg-[#ECFDF5] px-4 py-3.5 shadow-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[#10B981] text-white shadow-sm">
                <Shield size={18} />
              </div>
              <div>
                <div className="text-[10px] font-black uppercase text-[#059669]">
                  Favorable Fixtures
                </div>
                <div className="text-sm font-black text-[#0F172A]">
                  {summaryStats.favorableFixtures} Players
                </div>
              </div>
            </div>
          )}
          {summaryStats.inForm > 0 && (
            <div className="flex items-center gap-3.5 rounded-chunky-lg border border-indigo-200 bg-indigo-50 px-4 py-3.5 shadow-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm">
                <TrendingUp size={18} />
              </div>
              <div>
                <div className="text-[10px] font-black uppercase text-indigo-700">
                  Players In Form
                </div>
                <div className="text-sm font-black text-[#0F172A]">
                  {summaryStats.inForm} Improving
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
      {!loading && !error && (
        <div className="mb-4 text-xs font-bold text-[#64748B]">
          Showing {filtered.length} of {predictions.length} players
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
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

      {/* Player grid (No layout animation transitions) */}
      {!loading && !error && filtered.length > 0 && (
        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((p, i) => (
            <PlayerCard
              key={p.element ?? p.name}
              player={p}
              rank={i + 1}
              onClick={() => setSelected(p)}
            />
          ))}
        </div>
      )}

      {/* Player detail drawer */}
      <Drawer open={selected !== null} onClose={() => setSelected(null)}>
        {selected && <PlayerDetailPanel player={selected} />}
      </Drawer>
    </div>
  );
}
