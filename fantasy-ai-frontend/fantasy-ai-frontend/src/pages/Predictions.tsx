import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import { BarChart3, TrendingUp, Shield, Sparkles, Crown, LayoutGrid, List } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import { normalizePosition } from "@/hooks/useSquad";
import { PlayerCard } from "@/components/PlayerCard";
import { PredictionTable } from "@/components/PredictionTable";
import { FilterBar } from "@/components/FilterBar";
import { PlayerAvatar } from "@/components/identity";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";
import { formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

const SORT_OPTIONS = [
  { value: "predicted_fpl_rank_score", label: "Rank Score (Feedback 5)" },
  { value: "predicted_expected_points", label: "Expected Points (Safe)" },
  { value: "prob_high_score_6", label: "P(≥6 pts) Haul Chance" },
  { value: "prob_high_score_10", label: "P(≥10 pts) Ceiling Chance" },
  { value: "ceiling_p85", label: "P85 Upside Ceiling" },
  { value: "captaincy_score", label: "Captaincy Score" },
  { value: "predicted_total_points", label: "AI xPts (Standard)" },
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
  const [sortKey, setSortKey] = useState("predicted_fpl_rank_score");
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const [selected, setSelected] = useState<PlayerRecord | null>(null);

  const predictions = data?.predictions ?? [];
  const targetGw = data?.predicted_gameweek ?? predictions[0]?.predicted_for_gw;

  const topPicks = useMemo(() => {
    if (predictions.length === 0) return [];
    return [...predictions]
      .sort((a, b) => {
        const av = a.predicted_fpl_rank_score ?? a.predicted_expected_points ?? a.predicted_total_points ?? 0;
        const bv = b.predicted_fpl_rank_score ?? b.predicted_expected_points ?? b.predicted_total_points ?? 0;
        return bv - av;
      })
      .slice(0, 5);
  }, [predictions]);

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
        if (sortKey === "predicted_fpl_rank_score") {
          const av = a.predicted_fpl_rank_score ?? a.predicted_expected_points ?? a.predicted_total_points ?? -Infinity;
          const bv = b.predicted_fpl_rank_score ?? b.predicted_expected_points ?? b.predicted_total_points ?? -Infinity;
          return bv - av;
        }
        if (sortKey === "ceiling_p85") {
          const av = a.ceiling_p85 ?? a.predicted_p85_points ?? -Infinity;
          const bv = b.ceiling_p85 ?? b.predicted_p85_points ?? -Infinity;
          return bv - av;
        }
        if (sortKey === "predicted_expected_points") {
          const av = a.predicted_expected_points ?? a.predicted_total_points ?? -Infinity;
          const bv = b.predicted_expected_points ?? b.predicted_total_points ?? -Infinity;
          return bv - av;
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
      const bestScore = best.predicted_fpl_rank_score ?? best.predicted_expected_points ?? best.predicted_total_points ?? -1;
      const pScore = p.predicted_fpl_rank_score ?? p.predicted_expected_points ?? p.predicted_total_points ?? -1;
      return pScore > bestScore ? p : best;
    }, null);
    const favorableFixtures = predictions.filter(
      (p) => typeof p.fixture_difficulty === "number" && p.fixture_difficulty <= 2,
    ).length;
    const highCeilingPlayers = predictions.filter(
      (p) => typeof p.prob_high_score_6 === "number" && p.prob_high_score_6 >= 0.35,
    ).length;

    return { topPlayer, favorableFixtures, highCeilingPlayers };
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
              {typeof targetGw === "number" && (
                <span className="ml-2.5 text-[#10B981] font-black">GW {targetGw}</span>
              )}
            </h1>
          </div>
        </div>
        <p className="mt-1 text-sm font-semibold text-[#475569]">
          {data?.predicted_gameweek && data?.latest_completed_gameweek
            ? `Next Gameweek: GW ${data.predicted_gameweek} • Data updated through GW ${data.latest_completed_gameweek}${data.season ? ` • Season ${data.season}` : ""}`
            : data?.predicted_for_gw_note ?? "AI-projected points for every tracked player."}
        </p>
      </div>

      {/* Top Picks Strip */}
      {!loading && !error && topPicks.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Crown size={18} className="text-[#F59E0B]" />
              <h2 className="text-xs font-black uppercase tracking-wider text-[#0F172A]">
                Feedback 5 Top Model Picks
              </h2>
            </div>
            <span className="text-xs font-semibold text-[#64748B]">
              Ranked by Ceiling-Weighted Score
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {topPicks.map((player, idx) => (
              <div
                key={player.element ?? player.name}
                onClick={() => setSelected(player)}
                className="flex flex-col rounded-chunky-lg border border-[#E2E8F0] bg-white p-3 shadow-sm hover:border-[#10B981] hover:shadow-md cursor-pointer transition-all"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#FEF3C7] text-[10px] font-mono font-black text-[#92400E]">
                    #{idx + 1}
                  </span>
                  <span className="rounded-full bg-[#F1F5F9] border border-[#CBD5E1] px-2 py-0.2 text-[9px] font-black uppercase text-[#334155]">
                    {player.position === "GKP" ? "GK" : player.position}
                  </span>
                </div>
                <div className="flex items-center gap-2.5 mb-2">
                  <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="sm" />
                  <div className="min-w-0 flex-1">
                    <div className="font-display font-black text-xs text-[#0F172A] truncate">
                      {player.name ?? "N/A"}
                    </div>
                    <div className="text-[10px] font-semibold text-[#64748B] truncate">
                      {player.team ?? ""}
                    </div>
                  </div>
                </div>
                <div className="mt-auto flex items-center justify-between pt-2 border-t border-[#F1F5F9] text-xs">
                  <span className="text-[10px] font-bold text-[#64748B]">Score</span>
                  <span className="font-mono font-black text-[#059669]">
                    {formatStat(player.predicted_fpl_rank_score ?? player.predicted_expected_points)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
                  Top Model Rank
                </div>
                <div className="truncate text-sm font-black text-[#0F172A]">
                  {summaryStats.topPlayer.name ?? "N/A"}{" "}
                  <span className="numeral text-[#92400E] font-black">
                    {formatStat(summaryStats.topPlayer.predicted_fpl_rank_score ?? summaryStats.topPlayer.predicted_expected_points)} score
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
          {summaryStats.highCeilingPlayers > 0 && (
            <div className="flex items-center gap-3.5 rounded-chunky-lg border border-purple-200 bg-purple-50 px-4 py-3.5 shadow-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-purple-600 text-white shadow-sm">
                <TrendingUp size={18} />
              </div>
              <div>
                <div className="text-[10px] font-black uppercase text-purple-700">
                  High Ceiling Potential
                </div>
                <div className="text-sm font-black text-[#0F172A]">
                  {summaryStats.highCeilingPlayers} P(≥6) Candidates
                </div>
              </div>
            </div>
          )}
        </motion.div>
      )}

      {/* Filter bar & view toggle */}
      <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <FilterBar
          className="flex-1"
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

        {/* View mode toggle */}
        <div className="flex items-center gap-1 self-start lg:self-auto rounded-xl border border-[#CBD5E1] bg-[#F1F5F9] p-1 shadow-sm">
          <button
            type="button"
            onClick={() => setViewMode("grid")}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-black transition-all",
              viewMode === "grid"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#64748B] hover:text-[#0F172A]"
            )}
          >
            <LayoutGrid size={14} />
            <span>Cards</span>
          </button>
          <button
            type="button"
            onClick={() => setViewMode("table")}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-black transition-all",
              viewMode === "table"
                ? "bg-white text-[#0F172A] shadow-sm"
                : "text-[#64748B] hover:text-[#0F172A]"
            )}
          >
            <List size={14} />
            <span>Table</span>
          </button>
        </div>
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

      {/* Cards View */}
      {!loading && !error && filtered.length > 0 && viewMode === "grid" && (
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

      {/* Table View */}
      {!loading && !error && filtered.length > 0 && viewMode === "table" && (
        <PredictionTable
          players={filtered}
          onSelectPlayer={(p) => setSelected(p)}
        />
      )}

      {/* Player detail drawer */}
      <Drawer open={selected !== null} onClose={() => setSelected(null)}>
        {selected && <PlayerDetailPanel player={selected} />}
      </Drawer>
    </div>
  );
}
