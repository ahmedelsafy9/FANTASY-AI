import { useMemo, useState } from "react";
import {
  Trophy,
  Search,
  Sparkles,
  Flame,
  Shield,
  Calendar,
} from "lucide-react";
import type { MatchPrediction } from "@/types/api";
import { useMatchPredictions } from "@/hooks/useApi";
import { MatchCard } from "@/components/MatchCard";
import { MatchDetailPanel } from "@/components/MatchDetailPanel";
import { Drawer } from "@/components/ui/overlays";
import { ErrorState, EmptyState } from "@/components/states";
import { Skeleton } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

function MatchCardSkeleton() {
  return (
    <div className="flex flex-col rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-card space-y-4">
      <div className="flex justify-between items-center border-b border-[#F1F5F9] pb-3">
        <Skeleton className="h-5 w-20 rounded-md" />
        <Skeleton className="h-5 w-24 rounded-full" />
      </div>
      <div className="grid grid-cols-7 gap-2 items-center py-2">
        <div className="col-span-3 space-y-2">
          <Skeleton className="h-8 w-28 rounded-md" />
          <Skeleton className="h-4 w-12 rounded" />
        </div>
        <div className="col-span-1 flex flex-col items-center space-y-1">
          <Skeleton className="h-6 w-10 rounded-md" />
          <Skeleton className="h-3 w-14 rounded-full" />
        </div>
        <div className="col-span-3 flex flex-col items-end space-y-2">
          <Skeleton className="h-8 w-28 rounded-md" />
          <Skeleton className="h-4 w-12 rounded" />
        </div>
      </div>
      <Skeleton className="h-3 w-full rounded-full" />
      <div className="border-t border-[#F1F5F9] pt-3 flex justify-between">
        <Skeleton className="h-5 w-32 rounded-md" />
        <Skeleton className="h-5 w-16 rounded-md" />
      </div>
    </div>
  );
}

export default function MatchPredictions() {
  const { data, loading, error, refetch } = useMatchPredictions();
  const [query, setQuery] = useState("");
  const [resultFilter, setResultFilter] = useState<string>("ALL");
  const [confidenceFilter, setConfidenceFilter] = useState<string>("ALL");
  const [sortKey, setSortKey] = useState<string>("KICKOFF");
  const [selectedMatch, setSelectedMatch] = useState<MatchPrediction | null>(null);

  const predictions = data?.predictions ?? [];

  // Summary Highlights
  const summaryStats = useMemo(() => {
    if (predictions.length === 0) return null;

    // Highest Win Probability match
    const highestWinMatch = [...predictions].reduce((best, m) => {
      const bestP = Math.max(best.home_win_probability, best.away_win_probability);
      const mP = Math.max(m.home_win_probability, m.away_win_probability);
      return mP > bestP ? m : best;
    }, predictions[0]);

    const highestProbTeam =
      highestWinMatch.home_win_probability >= highestWinMatch.away_win_probability
        ? { team: highestWinMatch.home_team, prob: highestWinMatch.home_win_probability }
        : { team: highestWinMatch.away_team, prob: highestWinMatch.away_win_probability };

    // Highest Expected Goals match
    const highestXgMatch = [...predictions].reduce((best, m) => {
      const bestXg = best.predicted_home_goals + best.predicted_away_goals;
      const mXg = m.predicted_home_goals + m.predicted_away_goals;
      return mXg > bestXg ? m : best;
    }, predictions[0]);

    // Clean sheet favorite
    const cleanSheetFav = [...predictions].reduce((best, m) => {
      const bestCs = Math.max(best.home_clean_sheet_probability ?? 0, best.away_clean_sheet_probability ?? 0);
      const mCs = Math.max(m.home_clean_sheet_probability ?? 0, m.away_clean_sheet_probability ?? 0);
      return mCs > bestCs ? m : best;
    }, predictions[0]);

    const bestCsTeam =
      (cleanSheetFav.home_clean_sheet_probability ?? 0) >= (cleanSheetFav.away_clean_sheet_probability ?? 0)
        ? { team: cleanSheetFav.home_team, prob: cleanSheetFav.home_clean_sheet_probability ?? 0 }
        : { team: cleanSheetFav.away_team, prob: cleanSheetFav.away_clean_sheet_probability ?? 0 };

    return {
      highestProbTeam,
      highestWinMatch,
      highestXgMatch,
      bestCsTeam,
    };
  }, [predictions]);

  // Filtered and Sorted Matches
  const filteredMatches = useMemo(() => {
    return predictions
      .filter((m) => {
        if (!query.trim()) return true;
        const q = query.toLowerCase();
        return (
          m.home_team.toLowerCase().includes(q) ||
          m.away_team.toLowerCase().includes(q)
        );
      })
      .filter((m) => {
        if (resultFilter === "ALL") return true;
        return m.predicted_result === resultFilter;
      })
      .filter((m) => {
        if (confidenceFilter === "ALL") return true;
        return m.confidence_level === confidenceFilter;
      })
      .sort((a, b) => {
        if (sortKey === "CONFIDENCE") {
          return b.confidence - a.confidence;
        }
        if (sortKey === "TOTAL_XG") {
          const aXg = a.predicted_home_goals + a.predicted_away_goals;
          const bXg = b.predicted_home_goals + b.predicted_away_goals;
          return bXg - aXg;
        }
        if (sortKey === "HOME_PROB") {
          return b.home_win_probability - a.home_win_probability;
        }
        if (sortKey === "AWAY_PROB") {
          return b.away_win_probability - a.away_win_probability;
        }
        // Default: KICKOFF
        const aTime = a.kickoff_time ? new Date(a.kickoff_time).getTime() : 0;
        const bTime = b.kickoff_time ? new Date(b.kickoff_time).getTime() : 0;
        return aTime - bTime;
      });
  }, [predictions, query, resultFilter, confidenceFilter, sortKey]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 pb-safe-bottom sm:px-6 lg:px-8">
      {/* Header */}
      <div className="mb-6 flex flex-col gap-1">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] shadow-sm">
            <Trophy size={20} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-[#0F172A] sm:text-3xl">
              Match Predictions
              {data?.predicted_gameweek && (
                <span className="ml-2.5 text-[#10B981] font-black">
                  GW {data.predicted_gameweek}
                </span>
              )}
            </h1>
          </div>
        </div>
        <p className="mt-1 text-sm font-semibold text-[#475569]">
          {data?.predicted_gameweek && data?.latest_completed_gameweek
            ? `Upcoming Gameweek ${data.predicted_gameweek} Fixtures • Evaluated from official match data through GW ${data.latest_completed_gameweek}${
                data.season ? ` • Season ${data.season}` : ""
              }`
            : "Bivariate Poisson match outcome projections & market odds from the authoritative Match Model."}
        </p>
      </div>

      {/* Summary Highlight Strip */}
      {!loading && !error && summaryStats && (
        <div className="mb-6 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Card 1: Matches Evaluated */}
          <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-sm flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669]">
              <Calendar size={20} />
            </div>
            <div>
              <div className="text-[10px] font-black uppercase tracking-wider text-[#64748B]">
                Fixtures Analyzed
              </div>
              <div className="font-display text-lg font-black text-[#0F172A]">
                {data?.count ?? predictions.length} Matches
              </div>
              <div className="text-[11px] font-semibold text-[#10B981]">
                Full GW {data?.predicted_gameweek} Schedule
              </div>
            </div>
          </div>

          {/* Card 2: Highest Win Probability */}
          <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-sm flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#FEF3C7] text-[#D97706]">
              <Sparkles size={20} />
            </div>
            <div className="min-w-0">
              <div className="text-[10px] font-black uppercase tracking-wider text-[#64748B]">
                Strongest Favorite
              </div>
              <div className="font-display text-lg font-black text-[#0F172A] truncate">
                {summaryStats.highestProbTeam.team}
              </div>
              <div className="text-[11px] font-semibold text-[#D97706]">
                {Math.round(summaryStats.highestProbTeam.prob * 100)}% Win Probability
              </div>
            </div>
          </div>

          {/* Card 3: Highest xG Match */}
          <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-sm flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#FEF2F2] text-[#DC2626]">
              <Flame size={20} />
            </div>
            <div className="min-w-0">
              <div className="text-[10px] font-black uppercase tracking-wider text-[#64748B]">
                Projected Goal Fest
              </div>
              <div className="font-display text-sm font-black text-[#0F172A] truncate">
                {summaryStats.highestXgMatch.home_team} vs {summaryStats.highestXgMatch.away_team}
              </div>
              <div className="text-[11px] font-semibold text-[#DC2626]">
                {(
                  summaryStats.highestXgMatch.predicted_home_goals +
                  summaryStats.highestXgMatch.predicted_away_goals
                ).toFixed(2)}{" "}
                Combined xG
              </div>
            </div>
          </div>

          {/* Card 4: Clean Sheet Favorite */}
          <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-sm flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#EEF2FF] text-[#4F46E5]">
              <Shield size={20} />
            </div>
            <div className="min-w-0">
              <div className="text-[10px] font-black uppercase tracking-wider text-[#64748B]">
                Best Clean Sheet Odds
              </div>
              <div className="font-display text-lg font-black text-[#0F172A] truncate">
                {summaryStats.bestCsTeam.team}
              </div>
              <div className="text-[11px] font-semibold text-[#4F46E5]">
                {Math.round(summaryStats.bestCsTeam.prob * 100)}% Shutout Chance
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Filter and Control Bar */}
      <div className="mb-6 flex flex-col gap-3 rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-sm md:flex-row md:items-center md:justify-between">
        {/* Search */}
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94A3B8]"
          />
          <input
            type="text"
            placeholder="Search match or team..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-10 w-full rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] pl-10 pr-4 text-xs font-bold text-[#0F172A] placeholder-[#94A3B8] transition-all focus:border-[#10B981] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#10B981]/20"
          />
        </div>

        {/* Filters and Sort */}
        <div className="flex flex-wrap items-center gap-2">
          {/* Predicted Result Filter */}
          <div className="flex items-center rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] p-1 text-xs font-bold">
            <button
              onClick={() => setResultFilter("ALL")}
              className={cn(
                "rounded-lg px-2.5 py-1 transition-all cursor-pointer",
                resultFilter === "ALL"
                  ? "bg-white text-[#0F172A] shadow-sm font-black"
                  : "text-[#64748B] hover:text-[#0F172A]"
              )}
            >
              All Results
            </button>
            <button
              onClick={() => setResultFilter("HOME_WIN")}
              className={cn(
                "rounded-lg px-2.5 py-1 transition-all cursor-pointer",
                resultFilter === "HOME_WIN"
                  ? "bg-[#10B981] text-white shadow-sm font-black"
                  : "text-[#64748B] hover:text-[#0F172A]"
              )}
            >
              Home Wins
            </button>
            <button
              onClick={() => setResultFilter("DRAW")}
              className={cn(
                "rounded-lg px-2.5 py-1 transition-all cursor-pointer",
                resultFilter === "DRAW"
                  ? "bg-[#F59E0B] text-white shadow-sm font-black"
                  : "text-[#64748B] hover:text-[#0F172A]"
              )}
            >
              Draws
            </button>
            <button
              onClick={() => setResultFilter("AWAY_WIN")}
              className={cn(
                "rounded-lg px-2.5 py-1 transition-all cursor-pointer",
                resultFilter === "AWAY_WIN"
                  ? "bg-[#6366F1] text-white shadow-sm font-black"
                  : "text-[#64748B] hover:text-[#0F172A]"
              )}
            >
              Away Wins
            </button>
          </div>

          {/* Confidence Filter */}
          <div className="relative">
            <select
              value={confidenceFilter}
              onChange={(e) => setConfidenceFilter(e.target.value)}
              className="h-10 rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] px-3.5 pr-8 text-xs font-bold text-[#0F172A] transition-all focus:border-[#10B981] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#10B981]/20 cursor-pointer"
            >
              <option value="ALL">Confidence: All</option>
              <option value="HIGH">Confidence: High</option>
              <option value="MODERATE">Confidence: Moderate</option>
              <option value="LOW">Confidence: Low</option>
            </select>
          </div>

          {/* Sort Selector */}
          <div className="relative">
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value)}
              className="h-10 rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] px-3.5 pr-8 text-xs font-bold text-[#0F172A] transition-all focus:border-[#10B981] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#10B981]/20 cursor-pointer"
            >
              <option value="KICKOFF">Sort: Kickoff Time</option>
              <option value="CONFIDENCE">Sort: Model Confidence</option>
              <option value="TOTAL_XG">Sort: Highest Total Goals (xG)</option>
              <option value="HOME_PROB">Sort: Highest Home Win %</option>
              <option value="AWAY_PROB">Sort: Highest Away Win %</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Grid or Status States */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <MatchCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <ErrorState
          message={error || "Failed to load upcoming match predictions."}
          onRetry={refetch}
        />
      ) : filteredMatches.length === 0 ? (
        <EmptyState
          title="No matches found"
          description={
            query || resultFilter !== "ALL"
              ? "Try adjusting your search criteria or result filters."
              : "No upcoming match fixtures are scheduled for this Gameweek."
          }
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {filteredMatches.map((match) => (
            <MatchCard
              key={match.fixture_id}
              match={match}
              onClick={() => setSelectedMatch(match)}
            />
          ))}
        </div>
      )}

      {/* Match Detail Drawer */}
      <Drawer
        open={selectedMatch !== null}
        onClose={() => setSelectedMatch(null)}
      >
        <MatchDetailPanel match={selectedMatch} />
      </Drawer>
    </div>
  );
}
