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
  { id: "Elite Differential", label: "Elite Differentials", icon: Flame },
  { id: "Emerging Differential", label: "Emerging Stars", icon: Zap },
  { id: "Value Differential", label: "Budget Gems", icon: Coins },
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
    <div className="mx-auto max-w-7xl px-4 py-6 pb-safe-bottom sm:px-6 lg:px-8 space-y-6">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-chunky-xl border border-[#E2E8F0] bg-white p-6 md:p-8 shadow-card">
        <div className="absolute top-0 right-0 -mt-10 -mr-10 w-72 h-72 bg-[#ECFDF5] rounded-full blur-2xl opacity-70 pointer-events-none" />
        <div className="relative z-10 flex flex-col lg:flex-row lg:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-black bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] shadow-sm">
              <Sparkles className="w-3.5 h-3.5 fill-[#10B981] text-[#10B981]" />
              Gameweek {targetGw} Breakout Intelligence
            </div>
            <h1 className="font-display text-2xl md:text-3xl lg:text-4xl font-black tracking-tight text-[#0F172A]">
              High-Upside <span className="text-[#10B981]">Differentials</span>
            </h1>
            <p className="text-sm font-semibold text-[#475569] max-w-2xl leading-relaxed">
              Low-ownership picks (<span className="text-[#10B981] font-black">≤20% owned</span>) with strong expected points and high haul potential to help you gain rank this gameweek.
            </p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 shrink-0">
            <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-chunky p-3 text-center shadow-soft">
              <p className="text-[10px] font-black uppercase tracking-wider text-[#64748B]">Candidates</p>
              <p className="text-2xl font-mono font-black text-[#0F172A] mt-0.5">{kpis.total}</p>
            </div>
            <div className="bg-[#FFFBEB] border border-[#FDE68A] rounded-chunky p-3 text-center shadow-soft">
              <p className="text-[10px] font-black uppercase tracking-wider text-[#92400E]">Elite Picks</p>
              <p className="text-2xl font-mono font-black text-[#B45309] mt-0.5">{kpis.elite}</p>
            </div>
            <div className="bg-[#F0FDF4] border border-[#BBF7D0] rounded-chunky p-3 text-center shadow-soft">
              <p className="text-[10px] font-black uppercase tracking-wider text-[#15803D]">Avg Own %</p>
              <p className="text-2xl font-mono font-black text-[#16A34A] mt-0.5">{kpis.avgOwn}%</p>
            </div>
            <div className="bg-[#EEF2FF] border border-[#C7D2FE] rounded-chunky p-3 text-center shadow-soft">
              <p className="text-[10px] font-black uppercase tracking-wider text-[#3730A3]">Peak P(≥8)</p>
              <p className="text-2xl font-mono font-black text-[#4F46E5] mt-0.5">{kpis.maxUpside}%</p>
            </div>
          </div>
        </div>
      </div>

      {/* Top 3 Featured Breakout Cards */}
      {top3.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 font-display text-sm font-black text-[#0F172A] uppercase tracking-wider">
            <Flame className="w-4 h-4 text-[#F59E0B]" />
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
                  "relative rounded-chunky-lg border p-5 transition-all shadow-card hover:shadow-card-hover flex flex-col justify-between",
                  idx === 0
                    ? "bg-gradient-to-br from-[#ECFDF5]/50 via-white to-white border-2 border-[#10B981] shadow-card-playful"
                    : "bg-white border-[#E2E8F0] hover:border-[#CBD5E1]"
                )}
              >
                {idx === 0 && (
                  <div className="absolute -top-3 right-4 rounded-full bg-[#10B981] px-2.5 py-0.5 text-[10px] font-black uppercase text-white shadow-sm">
                    #1 Breakout Pick
                  </div>
                )}
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <PlayerAvatar
                      photoUrl={player.photo_url}
                      name={player.name}
                      className="w-12 h-12 rounded-xl shadow-sm border border-[#E2E8F0]"
                    />
                    <div>
                      <div className="flex items-center gap-1.5">
                        <h3 className="font-display font-black text-base text-[#0F172A]">{player.name}</h3>
                        <span className="text-[10px] font-black px-2 py-0.5 rounded-full bg-[#F1F5F9] border border-[#CBD5E1] text-[#334155] uppercase">
                          {player.position}
                        </span>
                      </div>
                      <p className="text-xs font-semibold text-[#64748B]">{player.team}</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] font-black uppercase tracking-wider text-[#059669]">Diff Score</span>
                    <p className="text-xl font-mono font-black text-[#059669]">{player.differential_score.toFixed(1)}</p>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#F1F5F9] grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2">
                    <span className="text-[10px] font-bold text-[#64748B] block">Price</span>
                    <span className="font-mono font-black text-[#0F172A]">£{player.price ?? ((player.value ?? 50) / 10).toFixed(1)}m</span>
                  </div>
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2">
                    <span className="text-[10px] font-bold text-[#64748B] block">Ownership</span>
                    <span className="font-mono font-black text-[#0284C7]">
                      {(player.ownership_pct ?? ((player.ownership_percentile ?? 0.1) * 100)).toFixed(1)}%
                    </span>
                  </div>
                  <div className="bg-[#F8FAFC] border border-[#E2E8F0] rounded-xl p-2">
                    <span className="text-[10px] font-bold text-[#64748B] block">Haul Chance</span>
                    <span className="font-mono font-black text-[#059669]">{((player.p_8_plus ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-between text-xs">
                  <span className={cn(
                    "px-2.5 py-1 rounded-full text-[10px] font-black uppercase border tracking-wider",
                    player.differential_category === "Elite Differential" && "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
                    player.differential_category === "Emerging Differential" && "bg-[#EEF2FF] text-[#3730A3] border-[#C7D2FE]",
                    player.differential_category === "Value Differential" && "bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]",
                    (!player.differential_category || player.differential_category === "Standard Differential") && "bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]",
                  )}>
                    {player.differential_category || "Standard"}
                  </span>
                  <span className="text-xs font-semibold text-[#64748B]">
                    Expected: <strong className="font-black text-[#0F172A]">{(player.predicted_expected_points ?? 0).toFixed(1)} pts</strong>
                  </span>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}

      {/* Filter and Control Bar */}
      <div className="space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-4 rounded-chunky-lg border border-[#E2E8F0] shadow-card">
          {/* Category Tabs */}
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => {
              const isSelected = selectedCategory === cat.id;
              const Icon = cat.icon;
              return (
                <button
                  key={cat.id}
                  onClick={() => setSelectedCategory(cat.id)}
                  className={cn(
                    "px-3.5 py-1.5 rounded-xl text-xs font-bold transition-all flex items-center gap-1.5",
                    isSelected
                      ? "bg-[#0F172A] text-white shadow-sm"
                      : "bg-[#F8FAFC] text-[#475569] border border-[#E2E8F0] hover:bg-[#F1F5F9] hover:text-[#0F172A]"
                  )}
                >
                  {Icon && <Icon className={cn("w-3.5 h-3.5", isSelected ? "text-white" : "text-[#64748B]")} />}
                  {cat.label}
                </button>
              );
            })}
          </div>

          {/* View toggle & search */}
          <div className="flex items-center gap-3">
            <div className="relative flex-1 md:w-60">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#94A3B8]" />
              <input
                type="text"
                placeholder="Search player or team..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full bg-[#F8FAFC] border border-[#CBD5E1] rounded-xl pl-9 pr-3 py-1.5 text-xs font-semibold text-[#0F172A] placeholder-[#94A3B8] focus:outline-none focus:border-[#10B981] focus:bg-white transition-colors"
              />
            </div>

            <div className="flex items-center bg-[#F1F5F9] border border-[#E2E8F0] rounded-xl p-0.5">
              <button
                onClick={() => setViewMode("grid")}
                className={cn(
                  "p-1.5 rounded-lg text-xs transition-all",
                  viewMode === "grid" ? "bg-white text-[#0F172A] shadow-sm" : "text-[#64748B] hover:text-[#0F172A]"
                )}
                title="Grid View"
              >
                <LayoutGrid className="w-4 h-4" />
              </button>
              <button
                onClick={() => setViewMode("table")}
                className={cn(
                  "p-1.5 rounded-lg text-xs transition-all",
                  viewMode === "table" ? "bg-white text-[#0F172A] shadow-sm" : "text-[#64748B] hover:text-[#0F172A]"
                )}
                title="Table View"
              >
                <List className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>

        {/* Secondary filters: Position & Ownership Threshold */}
        <div className="flex flex-wrap items-center gap-4 text-xs font-semibold text-[#64748B]">
          <div className="flex items-center gap-2">
            <span className="text-[#475569] font-bold">Position:</span>
            {["all", "GKP", "DEF", "MID", "FWD"].map((pos) => (
              <button
                key={pos}
                onClick={() => setSelectedPosition(pos)}
                className={cn(
                  "px-2.5 py-1 rounded-lg text-xs font-bold transition-all",
                  selectedPosition === pos
                    ? "bg-[#0F172A] text-white shadow-sm"
                    : "bg-white border border-[#E2E8F0] text-[#475569] hover:border-[#CBD5E1] hover:text-[#0F172A]"
                )}
              >
                {pos.toUpperCase()}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[#475569] font-bold">Ownership Cutoff:</span>
            {[10, 15, 20, 25, 100].map((own) => (
              <button
                key={own}
                onClick={() => setMaxOwnership(own)}
                className={cn(
                  "px-2.5 py-1 rounded-lg text-xs font-bold transition-all",
                  maxOwnership === own
                    ? "bg-[#10B981] text-white shadow-sm"
                    : "bg-white border border-[#E2E8F0] text-[#475569] hover:border-[#CBD5E1] hover:text-[#0F172A]"
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
              className="bg-white border border-[#E2E8F0] hover:border-[#10B981] rounded-chunky-lg p-4 transition-all shadow-card hover:shadow-card-hover flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    <PlayerAvatar
                      photoUrl={player.photo_url}
                      name={player.name}
                      className="w-10 h-10 rounded-xl border border-[#E2E8F0] shadow-sm"
                    />
                    <div>
                      <h4 className="font-display font-black text-sm text-[#0F172A] line-clamp-1">{player.name}</h4>
                      <p className="text-xs font-semibold text-[#64748B]">
                        {player.team} • <span className="font-bold text-[#334155]">{player.position}</span>
                      </p>
                    </div>
                  </div>
                  <span className="text-xs font-mono font-black text-[#059669] bg-[#ECFDF5] px-2 py-0.5 rounded-lg border border-[#A7F3D0]">
                    {player.differential_score.toFixed(1)}
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-1.5 text-center text-xs">
                  <div className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-lg p-1.5">
                    <span className="text-[10px] font-bold text-[#64748B] block">Price</span>
                    <span className="font-mono font-bold text-[#0F172A]">
                      £{player.price ?? ((player.value ?? 50) / 10).toFixed(1)}m
                    </span>
                  </div>
                  <div className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-lg p-1.5">
                    <span className="text-[10px] font-bold text-[#64748B] block">Ownership</span>
                    <span className="font-mono font-bold text-[#0284C7]">
                      {(player.ownership_pct ?? ((player.ownership_percentile ?? 0.1) * 100)).toFixed(1)}%
                    </span>
                  </div>
                  <div className="bg-[#F8FAFC] border border-[#F1F5F9] rounded-lg p-1.5">
                    <span className="text-[10px] font-bold text-[#64748B] block">xPts</span>
                    <span className="font-mono font-bold text-[#059669]">
                      {(player.predicted_expected_points ?? 0).toFixed(1)}
                    </span>
                  </div>
                </div>

                {/* Probability Chain Bars */}
                <div className="mt-3 space-y-1.5 text-[11px]">
                  <div className="flex items-center justify-between font-semibold text-[#475569]">
                    <span>Haul chance (8+ pts)</span>
                    <span className="font-mono font-bold text-[#059669]">{((player.p_8_plus ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-[#F1F5F9] rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-[#10B981] h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, (player.p_8_plus ?? 0) * 100 * 2.5)}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between font-semibold text-[#475569] pt-1">
                    <span>Ceiling chance (10+ pts)</span>
                    <span className="font-mono font-bold text-[#4F46E5]">{((player.p_10_plus ?? 0) * 100).toFixed(0)}%</span>
                  </div>
                  <div className="w-full bg-[#F1F5F9] rounded-full h-1.5 overflow-hidden">
                    <div
                      className="bg-[#6366F1] h-full rounded-full transition-all"
                      style={{ width: `${Math.min(100, (player.p_10_plus ?? 0) * 100 * 3.5)}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="mt-4 pt-2.5 border-t border-[#F1F5F9] flex items-center justify-between">
                <span className={cn(
                  "text-[10px] font-black uppercase px-2 py-0.5 rounded-full border tracking-wider",
                  player.differential_category === "Elite Differential" && "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
                  player.differential_category === "Emerging Differential" && "bg-[#EEF2FF] text-[#3730A3] border-[#C7D2FE]",
                  player.differential_category === "Value Differential" && "bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]",
                  (!player.differential_category || player.differential_category === "Standard Differential") && "bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]",
                )}>
                  {player.differential_category || "Standard"}
                </span>
                <span className="text-[10px] font-bold text-[#94A3B8]">
                  GW{targetGw}
                </span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        /* Table View */
        <div className="overflow-x-auto rounded-chunky-lg border border-[#E2E8F0] bg-white shadow-card">
          <table className="w-full text-left text-xs">
            <thead className="bg-[#F8FAFC] text-[#475569] uppercase font-black tracking-wider text-[11px] border-b border-[#E2E8F0]">
              <tr>
                <th className="py-3 px-4">Player</th>
                <th className="py-3 px-3">Team</th>
                <th className="py-3 px-3">Pos</th>
                <th className="py-3 px-3 text-right">Price</th>
                <th className="py-3 px-3 text-right">Own %</th>
                <th className="py-3 px-3 text-right">xPts</th>
                <th className="py-3 px-3 text-right">Return (6+)</th>
                <th className="py-3 px-3 text-right">Haul (8+)</th>
                <th className="py-3 px-3 text-right">Ceiling (10+)</th>
                <th className="py-3 px-4 text-right">Diff Rating</th>
                <th className="py-3 px-4">Category</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9]">
              {filtered.map((player) => (
                <tr key={player.element ?? player.name} className="hover:bg-[#F8FAFC] transition-colors">
                  <td className="py-3 px-4 font-bold text-[#0F172A] flex items-center gap-2.5">
                    <PlayerAvatar
                      photoUrl={player.photo_url}
                      name={player.name}
                      className="w-7 h-7 rounded-lg border border-[#E2E8F0]"
                    />
                    {player.name}
                  </td>
                  <td className="py-3 px-3 font-semibold text-[#64748B]">{player.team}</td>
                  <td className="py-3 px-3 font-bold text-[#334155]">{player.position}</td>
                  <td className="py-3 px-3 text-right font-mono font-semibold text-[#0F172A]">£{player.price ?? ((player.value ?? 50) / 10).toFixed(1)}m</td>
                  <td className="py-3 px-3 text-right font-mono font-bold text-[#0284C7]">
                    {(player.ownership_pct ?? ((player.ownership_percentile ?? 0.1) * 100)).toFixed(1)}%
                  </td>
                  <td className="py-3 px-3 text-right font-mono font-bold text-[#059669]">
                    {(player.predicted_expected_points ?? 0).toFixed(1)}
                  </td>
                  <td className="py-3 px-3 text-right font-mono text-[#64748B]">{((player.p_6_plus ?? 0) * 100).toFixed(0)}%</td>
                  <td className="py-3 px-3 text-right font-mono font-bold text-[#059669]">{((player.p_8_plus ?? 0) * 100).toFixed(0)}%</td>
                  <td className="py-3 px-3 text-right font-mono font-bold text-[#4F46E5]">{((player.p_10_plus ?? 0) * 100).toFixed(0)}%</td>
                  <td className="py-3 px-4 text-right font-mono font-black text-[#059669]">{player.differential_score.toFixed(1)}</td>
                  <td className="py-3 px-4">
                    <span className={cn(
                      "text-[10px] font-black uppercase px-2 py-0.5 rounded-full border tracking-wider",
                      player.differential_category === "Elite Differential" && "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
                      player.differential_category === "Emerging Differential" && "bg-[#EEF2FF] text-[#3730A3] border-[#C7D2FE]",
                      player.differential_category === "Value Differential" && "bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]",
                      (!player.differential_category || player.differential_category === "Standard Differential") && "bg-[#F1F5F9] text-[#475569] border-[#E2E8F0]",
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
