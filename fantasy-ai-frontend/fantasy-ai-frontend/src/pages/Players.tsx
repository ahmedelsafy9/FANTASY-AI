import { useMemo, useState } from "react";
import {
  Users,
  Search,
  LayoutGrid,
  List,
  Sparkles,
  DollarSign,
  TrendingUp,
} from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import { normalizePosition, getPlayerPrice } from "@/hooks/useSquad";
import { PlayerCard } from "@/components/PlayerCard";
import { PredictionTable } from "@/components/PredictionTable";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";
import { Drawer } from "@/components/ui/overlays";
import { Dropdown } from "@/components/ui/overlays";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { Button } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const SORT_OPTIONS = [
  { value: "xPts_desc", label: "Expected Points (High to Low)" },
  { value: "value_ratio", label: "Best Value (xPts / £m)" },
  { value: "form_desc", label: "Recent Form (3 GW)" },
  { value: "price_desc", label: "Price (High to Low)" },
  { value: "price_asc", label: "Price (Low to High)" },
  { value: "name_asc", label: "Name (A to Z)" },
];

const MAX_PRICE_OPTIONS = [
  { value: "all", label: "Any Price" },
  { value: "12.0", label: "Under £12.0m" },
  { value: "10.0", label: "Under £10.0m" },
  { value: "8.0", label: "Under £8.0m" },
  { value: "6.5", label: "Under £6.5m" },
  { value: "5.0", label: "Under £5.0m" },
  { value: "4.5", label: "Under £4.5m" },
];

const INITIAL_PAGE_SIZE = 24;

export default function Players() {
  const { data, loading, error, refetch } = usePredictions();
  const [query, setQuery] = useState("");
  const [position, setPosition] = useState("all");
  const [team, setTeam] = useState("all");
  const [maxPrice, setMaxPrice] = useState("all");
  const [sortKey, setSortKey] = useState("xPts_desc");
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");
  const [selectedPlayer, setSelectedPlayer] = useState<PlayerRecord | null>(null);
  const [visibleCount, setVisibleCount] = useState(INITIAL_PAGE_SIZE);

  const players = data?.predictions ?? [];
  const targetGw = data?.predicted_gameweek ?? players[0]?.predicted_for_gw ?? 1;

  // Unique teams for filter dropdown
  const teamOptions = useMemo(() => {
    const teams = Array.from(new Set(players.map((p) => p.team).filter(Boolean))) as string[];
    return [
      { value: "all", label: "All Teams" },
      ...teams.sort().map((t) => ({ value: t, label: t })),
    ];
  }, [players]);

  // KPIs
  const kpis = useMemo(() => {
    if (players.length === 0) return null;

    // Top projected pick
    const topPick = [...players].sort((a, b) => {
      const aX = a.predicted_expected_points ?? a.predicted_total_points ?? 0;
      const bX = b.predicted_expected_points ?? b.predicted_total_points ?? 0;
      return bX - aX;
    })[0];

    // Top budget gem (price <= 6.0)
    const budgetPicks = players.filter((p) => getPlayerPrice(p) <= 6.0);
    const topBudget = budgetPicks.sort((a, b) => {
      const aX = a.predicted_expected_points ?? a.predicted_total_points ?? 0;
      const bX = b.predicted_expected_points ?? b.predicted_total_points ?? 0;
      return bX - aX;
    })[0];

    return {
      total: players.length,
      topPick,
      topBudget,
    };
  }, [players]);

  // Filtered & Sorted
  const filtered = useMemo(() => {
    return players
      .filter((p) => {
        if (position === "all") return true;
        return normalizePosition(p.position) === normalizePosition(position);
      })
      .filter((p) => {
        if (team === "all") return true;
        return p.team === team;
      })
      .filter((p) => {
        if (maxPrice === "all") return true;
        const limit = parseFloat(maxPrice);
        return getPlayerPrice(p) <= limit;
      })
      .filter((p) => {
        if (!query.trim()) return true;
        const q = query.toLowerCase();
        return (
          p.name?.toLowerCase().includes(q) ||
          p.team?.toLowerCase().includes(q)
        );
      })
      .sort((a, b) => {
        const aX = a.predicted_expected_points ?? a.predicted_total_points ?? 0;
        const bX = b.predicted_expected_points ?? b.predicted_total_points ?? 0;
        const aPrice = getPlayerPrice(a);
        const bPrice = getPlayerPrice(b);

        if (sortKey === "xPts_desc") return bX - aX;
        if (sortKey === "value_ratio") {
          const aRatio = aPrice > 0 ? aX / aPrice : 0;
          const bRatio = bPrice > 0 ? bX / bPrice : 0;
          return bRatio - aRatio;
        }
        if (sortKey === "form_desc") {
          const aF = a.total_points_avg_last_3 ?? 0;
          const bF = b.total_points_avg_last_3 ?? 0;
          return bF - aF;
        }
        if (sortKey === "price_desc") return bPrice - aPrice;
        if (sortKey === "price_asc") return aPrice - bPrice;
        if (sortKey === "name_asc") {
          return String(a.name ?? "").localeCompare(String(b.name ?? ""));
        }
        return bX - aX;
      });
  }, [players, position, team, maxPrice, query, sortKey]);

  const visiblePlayers = useMemo(() => {
    return filtered.slice(0, visibleCount);
  }, [filtered, visibleCount]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-safe-bottom sm:px-6 lg:px-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#EEE7FA] text-[#452477] border border-[#D4C3ED] shadow-sm">
            <Users size={20} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-[#19171D] sm:text-3xl">
              Find Your Next Pick
            </h1>
            <p className="text-sm font-semibold text-[#6F6A76]">
              Compare expected points, confidence signals, and fixtures to find the best transfer for Gameweek {targetGw}.
            </p>
          </div>
        </div>
      </div>

      {/* KPI Highlight Strip */}
      {!loading && !error && kpis && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div className="rounded-xl border border-[#E8E3ED] bg-white p-4 shadow-sm flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#EEE7FA] text-[#452477] border border-[#D4C3ED]">
              <Sparkles size={18} />
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-black uppercase tracking-wider text-[#6F6A76]">
                #1 Expected Scorer
              </span>
              <div className="font-display font-black text-sm text-[#19171D] truncate">
                {kpis.topPick?.name}
              </div>
              <div className="text-[11px] font-bold text-[#452477]">
                {Math.round(kpis.topPick?.predicted_expected_points ?? kpis.topPick?.predicted_total_points ?? 0)} Expected Pts
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[#E8E3ED] bg-white p-4 shadow-sm flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#FDF8EC] text-[#8C680E] border border-[#E5D08E]">
              <DollarSign size={18} />
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-black uppercase tracking-wider text-[#8C680E]">
                Top Budget Gem (≤£6.0m)
              </span>
              <div className="font-display font-black text-sm text-[#19171D] truncate">
                {kpis.topBudget?.name}
              </div>
              <div className="text-[11px] font-bold text-[#8C680E]">
                £{getPlayerPrice(kpis.topBudget).toFixed(1)}m • {Math.round(kpis.topBudget?.predicted_expected_points ?? 0)} xPts
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[#E8E3ED] bg-white p-4 shadow-sm flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#EEF7FC] text-[#1E4D6B] border border-[#B9DDF5]">
              <TrendingUp size={18} />
            </div>
            <div>
              <span className="text-[10px] font-black uppercase tracking-wider text-[#6F6A76]">
                Players Tracked
              </span>
              <div className="font-display font-black text-base text-[#19171D]">
                {kpis.total} Premier League Assets
              </div>
              <div className="text-[11px] font-semibold text-[#6F6A76]">
                Live fixture analysis
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Control / Filter Bar */}
      <div className="space-y-3 rounded-2xl border border-[#E8E3ED] bg-white p-4 shadow-sm">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#6F6A76]" />
            <input
              type="text"
              placeholder="Search player or team..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setVisibleCount(INITIAL_PAGE_SIZE);
              }}
              className="h-10 w-full rounded-xl border border-[#E8E3ED] bg-[#F8F7FA] pl-10 pr-4 text-xs font-bold text-[#19171D] placeholder-[#6F6A76] transition-all focus:border-[#7041C5] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#7041C5]/20"
            />
          </div>

          {/* Position Pills */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0">
            {["all", "FWD", "MID", "DEF", "GKP"].map((pos) => {
              const label = pos === "all" ? "All" : pos === "GKP" ? "GK" : pos;
              const isSelected = position === pos;
              return (
                <button
                  key={pos}
                  onClick={() => {
                    setPosition(pos);
                    setVisibleCount(INITIAL_PAGE_SIZE);
                  }}
                  className={cn(
                    "px-3 py-2 rounded-xl text-xs font-black transition-all cursor-pointer",
                    isSelected
                      ? "bg-[#7041C5] text-white shadow-sm"
                      : "bg-[#F8F7FA] text-[#6F6A76] border border-[#E8E3ED] hover:bg-[#EEE7FA] hover:text-[#452477]"
                  )}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center bg-[#F4F3F6] border border-[#E8E3ED] rounded-xl p-1 self-start md:self-auto">
            <button
              onClick={() => setViewMode("grid")}
              className={cn(
                "p-1.5 rounded-lg text-xs transition-all cursor-pointer",
                viewMode === "grid" ? "bg-white text-[#19171D] shadow-sm font-black" : "text-[#6F6A76] hover:text-[#19171D]"
              )}
              title="Cards Grid View"
            >
              <LayoutGrid size={16} />
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={cn(
                "p-1.5 rounded-lg text-xs transition-all cursor-pointer",
                viewMode === "table" ? "bg-white text-[#19171D] shadow-sm font-black" : "text-[#6F6A76] hover:text-[#19171D]"
              )}
              title="Detailed Table View"
            >
              <List size={16} />
            </button>
          </div>
        </div>

        {/* Secondary Filter Row: Team, Max Price, Sort */}
        <div className="flex flex-wrap items-center gap-3 pt-2 border-t border-[#E8E3ED] text-xs">
          <div className="w-44">
            <Dropdown
              label="Team"
              options={teamOptions}
              value={team}
              onChange={(v) => {
                setTeam(v);
                setVisibleCount(INITIAL_PAGE_SIZE);
              }}
            />
          </div>

          <div className="w-44">
            <Dropdown
              label="Max Price"
              options={MAX_PRICE_OPTIONS}
              value={maxPrice}
              onChange={(v) => {
                setMaxPrice(v);
                setVisibleCount(INITIAL_PAGE_SIZE);
              }}
            />
          </div>

          <div className="w-56">
            <Dropdown
              label="Sort By"
              options={SORT_OPTIONS}
              value={sortKey}
              onChange={(v) => {
                setSortKey(v);
                setVisibleCount(INITIAL_PAGE_SIZE);
              }}
            />
          </div>

          <span className="ml-auto text-xs font-bold text-[#6F6A76]">
            Showing {Math.min(visibleCount, filtered.length)} of {filtered.length} players
          </span>
        </div>
      </div>

      {/* Main Player List */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <PlayerCardSkeleton key={i} />
          ))}
        </div>
      )}

      {!loading && error && (
        <ErrorState message={error} onRetry={refetch} />
      )}

      {!loading && !error && filtered.length === 0 && (
        <EmptyState
          title="No players found"
          description="Try clearing your search query or adjusting your position and price filters."
        />
      )}

      {!loading && !error && filtered.length > 0 && viewMode === "grid" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {visiblePlayers.map((player, idx) => (
              <PlayerCard
                key={player.element ?? player.name ?? idx}
                player={player}
                rank={idx + 1}
                onClick={() => setSelectedPlayer(player)}
              />
            ))}
          </div>

          {visibleCount < filtered.length && (
            <div className="flex justify-center pt-4">
              <Button
                variant="secondary"
                size="md"
                onClick={() => setVisibleCount((c) => c + INITIAL_PAGE_SIZE)}
                className="font-black px-6"
              >
                Load More Players ({filtered.length - visibleCount} remaining)
              </Button>
            </div>
          )}
        </div>
      )}

      {!loading && !error && filtered.length > 0 && viewMode === "table" && (
        <div className="space-y-6">
          <PredictionTable
            players={visiblePlayers}
            onSelectPlayer={(p) => setSelectedPlayer(p)}
          />

          {visibleCount < filtered.length && (
            <div className="flex justify-center pt-4">
              <Button
                variant="secondary"
                size="md"
                onClick={() => setVisibleCount((c) => c + INITIAL_PAGE_SIZE)}
                className="font-black px-6"
              >
                Load More Players ({filtered.length - visibleCount} remaining)
              </Button>
            </div>
          )}
        </div>
      )}

      {/* Player Detail Drawer */}
      <Drawer
        open={!!selectedPlayer}
        onClose={() => setSelectedPlayer(null)}
        title={selectedPlayer?.name ?? "Player Profile"}
      >
        {selectedPlayer && <PlayerDetailPanel player={selectedPlayer} />}
      </Drawer>
    </div>
  );
}
