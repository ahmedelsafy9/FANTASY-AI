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
  { value: "xPts_desc", label: "Predicted Points (High to Low)" },
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
      <div className="flex flex-col gap-1.5">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-stadium-deep text-gold-bright shadow-sm">
            <Users size={22} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-ink-primary sm:text-3xl tracking-tight">
              Player Projections &amp; Intelligence
            </h1>
            <p className="text-xs sm:text-sm font-semibold text-ink-secondary mt-0.5">
              Decision-oriented expected points, official fitness status, and upcoming opposition for Gameweek {targetGw}.
            </p>
          </div>
        </div>
      </div>

      {/* KPI Highlight Strip */}
      {!loading && !error && kpis && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5">
          <div className="rounded-2xl border border-gold-border bg-gold-light/60 p-4 shadow-card flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gold-metallic text-stadium-dark shadow-xs">
              <Sparkles size={18} />
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-black uppercase tracking-wider text-gold-dark">
                #1 Projected Scorer
              </span>
              <div className="font-display font-black text-base text-ink-primary truncate">
                {kpis.topPick?.name}
              </div>
              <div className="text-[11px] font-black text-gold-dark">
                {Math.round(kpis.topPick?.predicted_expected_points ?? kpis.topPick?.predicted_total_points ?? 0)} Expected Pts
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-ivory-surface p-4 shadow-card flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-stadium-surface/10 text-stadium-deep shadow-xs border border-border">
              <DollarSign size={18} />
            </div>
            <div className="min-w-0">
              <span className="text-[10px] font-black uppercase tracking-wider text-ink-secondary">
                Top Budget Pick (≤£6.0m)
              </span>
              <div className="font-display font-black text-base text-ink-primary truncate">
                {kpis.topBudget?.name}
              </div>
              <div className="text-[11px] font-bold text-ink-secondary">
                £{getPlayerPrice(kpis.topBudget).toFixed(1)}m • {Math.round(kpis.topBudget?.predicted_expected_points ?? 0)} xPts
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-border bg-ivory-surface p-4 shadow-card flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-stadium-deep text-ivory-surface shadow-xs">
              <TrendingUp size={18} />
            </div>
            <div>
              <span className="text-[10px] font-black uppercase tracking-wider text-ink-secondary">
                Premier League Assets
              </span>
              <div className="font-display font-black text-base text-ink-primary">
                {kpis.total} Tracked Players
              </div>
              <div className="text-[11px] font-semibold text-ink-secondary">
                Live FPL availability sync
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Control / Filter Bar */}
      <div className="space-y-3.5 rounded-2xl border border-border bg-ivory-surface p-4 shadow-card">
        <div className="flex flex-col md:flex-row gap-3">
          {/* Search */}
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-secondary" />
            <input
              type="text"
              placeholder="Search player or club..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setVisibleCount(INITIAL_PAGE_SIZE);
              }}
              className="h-10 w-full rounded-xl border border-border bg-ivory-subtle pl-10 pr-4 text-xs font-bold text-ink-primary placeholder-ink-secondary transition-all focus:border-gold-metallic focus:bg-ivory-surface focus:outline-none focus:ring-2 focus:ring-gold-metallic/30"
            />
          </div>

          {/* Position Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
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
                    "px-3.5 py-2 rounded-xl text-xs font-black transition-all cursor-pointer select-none",
                    isSelected
                      ? "bg-stadium-deep text-ivory-surface shadow-xs border border-stadium-surface"
                      : "bg-ivory-subtle text-ink-secondary border border-border hover:bg-ivory-surface hover:text-ink-primary",
                  )}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center bg-ivory-subtle border border-border rounded-xl p-1 self-start md:self-auto">
            <button
              onClick={() => setViewMode("grid")}
              className={cn(
                "p-1.5 rounded-lg text-xs transition-all cursor-pointer",
                viewMode === "grid" ? "bg-ivory-surface text-ink-primary shadow-xs font-black" : "text-ink-secondary hover:text-ink-primary",
              )}
              title="Cards Grid View"
            >
              <LayoutGrid size={16} />
            </button>
            <button
              onClick={() => setViewMode("table")}
              className={cn(
                "p-1.5 rounded-lg text-xs transition-all cursor-pointer",
                viewMode === "table" ? "bg-ivory-surface text-ink-primary shadow-xs font-black" : "text-ink-secondary hover:text-ink-primary",
              )}
              title="Detailed Table View"
            >
              <List size={16} />
            </button>
          </div>
        </div>

        {/* Secondary Filter Row: Team, Max Price, Sort */}
        <div className="flex flex-wrap items-center gap-3 pt-3 border-t border-border text-xs">
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

          <span className="ml-auto text-xs font-bold text-ink-secondary">
            Showing {Math.min(visibleCount, filtered.length)} of {filtered.length} players
          </span>
        </div>
      </div>

      {/* Main Player Display */}
      {loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
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
          title="No players match the current filters"
          description="Try adjusting your position, team, price threshold, or search keyword."
        />
      )}

      {!loading && !error && filtered.length > 0 && viewMode === "grid" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
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
                className="font-black px-8"
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
                className="font-black px-8"
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
