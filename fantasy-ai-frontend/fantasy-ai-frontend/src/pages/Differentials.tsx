import { useMemo, useState } from "react";
import { motion } from "framer-motion";
import {
  Sparkles,
  Flame,
  Coins,
  Search,
  LayoutGrid,
  List,
  Zap,
} from "lucide-react";
import { useDifferentials } from "@/hooks/useApi";
import { normalizePosition } from "@/hooks/useSquad";
import { PlayerAvatar } from "@/components/identity";
import { PlayerCardSkeleton, ErrorState, EmptyState } from "@/components/states";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { id: "all", label: "All Differentials" },
  { id: "Elite Differential", label: "Elite Differentials", icon: Flame, color: "text-amber-400 border-amber-500/30 bg-amber-500/10" },
  { id: "Emerging Differential", label: "Emerging Starts", icon: Zap, color: "text-cyan-400 border-cyan-500/30 bg-cyan-500/10" },
  { id: "Value Differential", label: "Budget Gems", icon: Coins, color: "text-emerald-400 border-emerald-500/30 bg-emerald-500/10" },
];

export default function Differentials() {
  const { data, loading, error, refetch } = useDifferentials();
  const [query, setQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [selectedPosition, setSelectedPosition] = useState("all");
  const [maxOwnership, setMaxOwnership] = useState<number>(25);
  const [viewMode, setViewMode] = useState<"grid" | "table">("grid");

  const predictions = data?.predictions ?? [];
  const targetGw = data?.predicted_gameweek ?? 1;

  const filtered = useMemo(() => {
    return predictions
      .filter((p) => {
        if (selectedCategory === "all") return true;
        return p.differential_category?.toLowerCase() === selectedCategory.toLowerCase();
      })
      .filter((p) => {
        if (selectedPosition === "all") return true;
        return normalizePosition(p.position ?? "") === normalizePosition(selectedPosition);
      })
      .filter((p) => {
        if (maxOwnership === 100) return true;
        const own = p.ownership_pct ?? (p.ownership_percentile ? p.ownership_percentile * 100 : 15);
        return own <= maxOwnership;
      })
      .filter((p) => {
        if (!query.trim()) return true;
        const q = query.toLowerCase();
        return (
          p.name.toLowerCase().includes(q) ||
          p.team.toLowerCase().includes(q) ||
          (p.position?.toLowerCase().includes(q) ?? false)
        );
      })
      .sort((a, b) => (b.differential_score ?? 0) - (a.differential_score ?? 0));
  }, [predictions, selectedCategory, selectedPosition, maxOwnership, query]);

  const top3 = useMemo(() => filtered.slice(0, 3), [filtered]);

  // Summary KPIs
  const kpis = useMemo(() => {
    const eliteCount = predictions.filter((p) => p.differential_category === "Elite Differential").length;
    const avgOwn = predictions.length > 0
      ? (predictions.reduce((acc, p) => acc + (p.ownership_pct ?? 10), 0) / predictions.length).toFixed(1)
      : "0.0";
    const maxUpside = predictions.length > 0
      ? Math.max(...predictions.map((p) => p.p_8_plus ?? 0))
      : 0;

    return {
      total: predictions.length,
      elite: eliteCount,
      avgOwn,
      maxUpside: (maxUpside * 100).toFixed(0),
    };
  }, [predictions]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 md:p-8 space-y-8">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-purple-900/40 via-indigo-900/30 to-slate-900/60 border border-purple-500/20 p-6 md:p-8 shadow-2xl backdrop-blur-xl">
        <div className="absolute top-0 right-0 -mt-8 -mr-8 w-64 h-64 bg-purple-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-purple-500/20 text-purple-300 border border-purple-500/30">
              <Sparkles className="w-3.5 h-3.5" />
              Gameweek {targetGw} Breakout Intelligence
            </div>
            <h1 className="text-3xl md:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-purple-200 bg-clip-text text-transparent">
              High-Upside Differentials
            </h1>
            <p className="text-sm md:text-base text-slate-400 max-w-2xl">
              Targeted prediction layer identifying low-ownership players (<span className="text-purple-300 font-medium">≤20%</span>)
              with disproportionate probability of outperforming expected output in the next Gameweek.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 text-center">
              <p className="text-xs text-slate-400 uppercase tracking-wider">Candidates</p>
              <p className="text-xl font-bold text-white mt-0.5">{kpis.total}</p>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 text-center">
              <p className="text-xs text-amber-400 uppercase tracking-wider">Elite Picks</p>
              <p className="text-xl font-bold text-amber-300 mt-0.5">{kpis.elite}</p>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 text-center">
              <p className="text-xs text-slate-400 uppercase tracking-wider">Avg Own %</p>
              <p className="text-xl font-bold text-cyan-300 mt-0.5">{kpis.avgOwn}%</p>
            </div>
            <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-3 text-center">
              <p className="text-xs text-purple-400 uppercase tracking-wider">Peak P(≥8)</p>
              <p className="text-xl font-bold text-purple-300 mt-0.5">{kpis.maxUpside}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Top 3 Featured Breakout Cards */}
      {top3.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-300 uppercase tracking-wider">
            <Flame className="w-4 h-4 text-amber-400" />
            Top Differential Breakthroughs of the Week
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
            {top3.map((player, idx) => (
              <motion.div
                key={player.element ?? player.name}
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.1 }}
                className={cn(
                  "relative rounded-xl border p-5 transition-all shadow-lg overflow-hidden",
                  idx === 0
                    ? "bg-gradient-to-b from-purple-900/30 to-slate-900/90 border-purple-500/40 shadow-purple-950/40"
                    : "bg-slate-900/80 border-slate-800/80 hover:border-slate-700"
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <PlayerAvatar
                      photoUrl={player.photo_url}
                      name={player.name}
                      className="w-12 h-12 rounded-lg"
                    />
                    <div>
                      <div className="flex items-center gap-1.5">
                        <h3 className="font-bold text-base text-white">{player.name}</h3>
                        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                          {player.position}
                        </span>
                      </div>
                      <p className="text-xs text-slate-400">{player.team}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-xs text-purple-300 font-medium">Diff Score</span>
                    <p className="text-xl font-extrabold text-purple-400">{player.differential_score.toFixed(1)}</p>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800/80 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="bg-slate-950/50 rounded-lg p-2">
                    <span className="text-slate-400 block">Price</span>
                    <span className="font-bold text-white">£{player.price ?? ((player.value ?? 50) / 10).toFixed(1)}m</span>
                  </div>
                  <div className="bg-slate-950/50 rounded-lg p-2">
                    <span className="text-slate-400 block">Ownership</span>
                    <span className="font-bold text-cyan-300">
                      {(player.ownership_pct ?? ((player.ownership_percentile ?? 0.1) * 100)).toFixed(1)}%
                    </span>
                  </div>
                  <div className="bg-slate-950/50 rounded-lg p-2">
                    <span className="text-slate-400 block">P(≥8 pts)</span>
                    <span className="font-bold text-emerald-400">{((player.p_8_plus ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between text-xs">
                  <span className={cn(
                    "px-2.5 py-1 rounded-md text-[11px] font-semibold border",
                    player.differential_category === "Elite Differential" && "bg-amber-500/10 text-amber-300 border-amber-500/30",
                    player.differential_category === "Emerging Differential" && "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
                    player.differential_category === "Value Differential" && "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
                    (!player.differential_category || player.differential_category === "Standard Differential") && "bg-slate-800 text-slate-300 border-slate-700",
                  )}>
                    {player.differential_category || "Standard Differential"}
                  </span>
                  <span className="text-slate-400">
                    Expected: <strong className="text-slate-200">{(player.predicted_expected_points ?? 0).toFixed(1)} pts</strong>
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Filter and Control Bar */}
      <div className="space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800/80">
          {/* Category Tabs */}
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => (
              <button
                key={cat.id}
                onClick={() => setSelectedCategory(cat.id)}
                className={cn(
                  "px-3 py-1.5 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5",
                  selectedCategory === cat.id
                    ? "bg-purple-600 text-white shadow-md shadow-purple-600/30"
                    : "bg-slate-800/80 text-slate-400 hover:text-slate-200 hover:bg-slate-800"
                )}
              >
                {cat.icon && <cat.icon className="w-3.5 h-3.5" />}
                {cat.label}
              </button>
            ))}
          </div>

          {/* View toggle & search */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1 md:w-56">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                type="text"
                placeholder="Search player or team..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="flex items-center bg-slate-950 border border-slate-800 rounded-lg p-0.5">
              <button
                onClick={() => setViewMode("grid")}
                className={cn(
                  "p-1.5 rounded-md text-xs transition-all",
                  viewMode === "grid" ? "bg-slate-800 text-white" : "text-slate-500 hover:text-slate-300"
                )}
                title="Grid View"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={cn(
                  "p-1.5 rounded-md text-xs transition-all",
                  viewMode === "table" ? "bg-slate-800 text-white" : "text-slate-500 hover:text-slate-300"
                )}
                title="Table View"
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Secondary filters: Position & Ownership Threshold */}
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400">
          <div className="flex items-center gap-2">
            <span>Position:</span>
            {["all", "GKP", "DEF", "MID", "FWD"].map((pos) => (
              <button
                key={pos}
                onClick={() => setSelectedPosition(pos)}
                className={cn(
                  "px-2.5 py-1 rounded text-xs font-medium transition-all",
                  selectedPosition === pos ? "bg-slate-700 text-white" : "bg-slate-900 text-slate-400 hover:text-white"
                )}
              >
                {pos.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <span>Ownership Cutoff:</span>
            {[10, 15, 20, 25, 100].map((own) => (
              <button
                key={own}
                onClick={() => setMaxOwnership(own)}
                className={cn(
                  "px-2.5 py-1 rounded text-xs font-medium transition-all",
                  maxOwnership === own ? "bg-purple-900/50 text-purple-300 border border-purple-500/40" : "bg-slate-900 text-slate-400 hover:text-white"
                )}
              >
                {own === 100 ? "Any" : `≤${own}%`}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {loading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <PlayerCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? (
        <ErrorState message={error} onRetry={refetch} />
      ) : filtered.length === 0 ? (
        <EmptyState
          title="No Differentials Found"
          description="Try adjusting your filters, ownership cutoff, or search query."
        />
      ) : viewMode === "grid" ? (
        /* Grid View */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {filtered.map((player) => (
            <div
              key={player.element ?? player.name}
              className="bg-slate-900/70 border border-slate-800/80 hover:border-purple-500/40 rounded-xl p-4 transition-all hover:shadow-xl hover:shadow-purple-950/20 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <PlayerAvatar
                      photoUrl={player.photo_url}
                      name={player.name}
                      className="w-10 h-10 rounded-lg"
                    />
                    <div>
                      <h4 className="font-bold text-sm text-white line-clamp-1">{player.name}</h4>
                      <p className="text-xs text-slate-400">
                        {player.team} • <span className="text-slate-300">{player.position}</span>
                      </p>
                    </div>
                  </div>
                  <span className="text-xs font-bold text-purple-400 bg-purple-500/10 px-2 py-0.5 rounded border border-purple-500/20">
                    {player.differential_score.toFixed(1)}
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-1.5 text-center text-xs">
                  <div className="bg-slate-950/60 rounded p-1.5">
                    <span className="text-[10px] text-slate-500 block">Price</span>
                    <span className="font-semibold text-slate-200">
                      £{player.price ?? ((player.value ?? 50) / 10).toFixed(1)}m
                    </span>
                  </div>
                  <div className="bg-slate-950/60 rounded p-1.5">
                    <span className="text-[10px] text-slate-500 block">Ownership</span>
                    <span className="font-semibold text-cyan-400">
                      {(player.ownership_pct ?? ((player.ownership_percentile ?? 0.1) * 100)).toFixed(1)}%
                    </span>
                  </div>
                  <div className="bg-slate-950/60 rounded p-1.5">
                    <span className="text-[10px] text-slate-500 block">xPts</span>
                    <span className="font-semibold text-slate-200">
                      {(player.predicted_expected_points ?? 0).toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* Probability Chain Bars */}
                <div className="mt-3 space-y-1 text-[11px]">
                  <div className="flex items-center justify-between text-slate-400">
                    <span>P(≥8 pts Haul)</span>
                    <span className="font-medium text-emerald-400">{((player.p_8_plus ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-emerald-500 h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, (player.p_8_plus ?? 0) * 100 * 2.5)}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-slate-400 pt-1">
                    <span>P(≥10 pts Ceiling)</span>
                    <span className="font-medium text-purple-400">{((player.p_10_plus ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-slate-950 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-purple-500 h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, (player.p_10_plus ?? 0) * 100 * 3.5)}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-2.5 border-t border-slate-800/80 flex items-center justify-between">
                <span className={cn(
                  "text-[10px] font-semibold px-2 py-0.5 rounded border",
                  player.differential_category === "Elite Differential" && "bg-amber-500/10 text-amber-300 border-amber-500/30",
                  player.differential_category === "Emerging Differential" && "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
                  player.differential_category === "Value Differential" && "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
                  (!player.differential_category || player.differential_category === "Standard Differential") && "bg-slate-800 text-slate-400 border-slate-700",
                )}>
                  {player.differential_category || "Standard"}
                </span>
                <span className="text-[10px] text-slate-500">
                  GW{targetGw}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-900/50">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-3 px-4">Player</th>
                <th className="py-3 px-3">Team</th>
                <th className="py-3 px-3">Pos</th>
                <th className="py-3 px-3 text-right">Price</th>
                <th className="py-3 px-3 text-right">Own %</th>
                <th className="py-3 px-3 text-right">xPts</th>
                <th className="py-3 px-3 text-right">P(≥6)</th>
                <th className="py-3 px-3 text-right">P(≥8)</th>
                <th className="py-3 px-3 text-right">P(≥10)</th>
                <th className="py-3 px-4 text-right">Diff Score</th>
                <th className="py-3 px-4">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filtered.map((player) => (
                <tr key={player.element ?? player.name} className="hover:bg-slate-800/40 transition-colors">
                  <td className="py-3 px-4 font-semibold text-white flex items-center gap-2.5">
                    <PlayerAvatar
                      photoUrl={player.photo_url}
                      name={player.name}
                      className="w-7 h-7 rounded"
                    />
                    {player.name}
                  </td>
                  <td className="py-3 px-3 text-slate-400">{player.team}</td>
                  <td className="py-3 px-3 text-slate-300 font-medium">{player.position}</td>
                  <td className="py-3 px-3 text-right font-medium">£{player.price ?? ((player.value ?? 50) / 10).toFixed(1)}m</td>
                  <td className="py-3 px-3 text-right font-semibold text-cyan-400">
                    {(player.ownership_pct ?? ((player.ownership_percentile ?? 0.1) * 100)).toFixed(1)}%
                  </td>
                  <td className="py-3 px-3 text-right font-medium text-slate-200">
                    {(player.predicted_expected_points ?? 0).toFixed(1)}
                  </td>
                  <td className="py-3 px-3 text-right text-slate-400">{((player.p_6_plus ?? 0) * 100).toFixed(0)}%</td>
                  <td className="py-3 px-3 text-right font-bold text-emerald-400">{((player.p_8_plus ?? 0) * 100).toFixed(0)}%</td>
                  <td className="py-3 px-3 text-right font-bold text-purple-400">{((player.p_10_plus ?? 0) * 100).toFixed(0)}%</td>
                  <td className="py-3 px-4 text-right font-extrabold text-purple-300">{player.differential_score.toFixed(1)}</td>
                  <td className="py-3 px-4">
                    <span className={cn(
                      "text-[10px] font-semibold px-2 py-0.5 rounded border",
                      player.differential_category === "Elite Differential" && "bg-amber-500/10 text-amber-300 border-amber-500/30",
                      player.differential_category === "Emerging Differential" && "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
                      player.differential_category === "Value Differential" && "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
                      (!player.differential_category || player.differential_category === "Standard Differential") && "bg-slate-800 text-slate-400 border-slate-700",
                    )}>
                      {player.differential_category || "Standard"}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
