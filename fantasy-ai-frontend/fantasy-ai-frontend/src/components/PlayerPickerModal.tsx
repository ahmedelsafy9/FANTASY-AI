import { useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  X,
  Plus,
  RefreshCw,
  Search,
  ArrowUpDown,
  ChevronDown,
  AlertCircle,
} from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { Skeleton } from "@/components/ui/primitives";
import { ErrorState, EmptyState } from "@/components/states";
import { formatPrice, formatInt } from "@/lib/format";
import {
  getPlayerId,
  getPlayerPrice,
  normalizePosition,
  useSquad,
} from "@/hooks/useSquad";
import { cn } from "@/lib/utils";

const POSITION_TABS = [
  { id: "all", label: "All" },
  { id: "GKP", label: "GK" },
  { id: "DEF", label: "DEF" },
  { id: "MID", label: "MID" },
  { id: "FWD", label: "FWD" },
] as const;

type SortKey = "prediction" | "price_desc" | "price_asc" | "form" | "value";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "prediction", label: "AI Prediction (High)" },
  { value: "price_desc", label: "Price (High to Low)" },
  { value: "price_asc", label: "Price (Low to High)" },
  { value: "form", label: "Form (Recent Points)" },
  { value: "value", label: "Best Value (xPts / £m)" },
];

function getAITag(
  pts: number | null | undefined,
): { label: string; tone: string } | null {
  if (pts === null || pts === undefined) return null;
  if (pts >= 7.5) return { label: "AI PICK", tone: "emerald" };
  if (pts >= 6.0) return { label: "STRONG", tone: "gold" };
  if (pts >= 4.5) return { label: "GOOD", tone: "sky" };
  return null;
}

interface PlayerPickerModalProps {
  open: boolean;
  onClose: () => void;
  targetPosition?: string;
  replacingPlayer?: PlayerRecord | null;
  players: PlayerRecord[];
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  sq: ReturnType<typeof useSquad>;
  onSelectPlayer: (player: PlayerRecord) => void;
}

export function PlayerPickerModal({
  open,
  onClose,
  targetPosition,
  replacingPlayer,
  players,
  loading,
  error,
  onRetry,
  sq,
  onSelectPlayer,
}: PlayerPickerModalProps) {
  const [posTab, setPosTab] = useState<string>("all");
  const [query, setQuery] = useState("");
  const [teamFilter, setTeamFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("prediction");
  const [showTeamMenu, setShowTeamMenu] = useState(false);
  const [showSortMenu, setShowSortMenu] = useState(false);

  // Sync position tab when targetPosition changes
  useEffect(() => {
    if (targetPosition) {
      const norm = normalizePosition(targetPosition);
      setPosTab(norm);
    } else {
      setPosTab("all");
    }
    setQuery("");
  }, [targetPosition, open]);

  // Close on Escape key
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    if (open) document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const teamOptions = useMemo(() => {
    const teams = Array.from(
      new Set(players.map((p) => p.team).filter(Boolean)),
    ) as string[];
    return [
      { value: "all", label: "All Clubs" },
      ...teams.sort().map((t) => ({ value: t, label: t })),
    ];
  }, [players]);

  const filteredPlayers = useMemo(() => {
    let list = players.filter((p) => {
      // Position filter
      if (posTab !== "all") {
        const norm = normalizePosition(p.position);
        if (norm !== posTab) return false;
      }
      // Team filter
      if (teamFilter !== "all" && p.team !== teamFilter) return false;
      // Query filter
      if (query.trim()) {
        const q = query.toLowerCase();
        const matchesName = p.name?.toLowerCase().includes(q);
        const matchesTeam = p.team?.toLowerCase().includes(q);
        if (!matchesName && !matchesTeam) return false;
      }
      return true;
    });

    list = [...list].sort((a, b) => {
      switch (sortKey) {
        case "prediction":
          return (
            (b.predicted_total_points ?? -100) -
            (a.predicted_total_points ?? -100)
          );
        case "price_desc":
          return getPlayerPrice(b) - getPlayerPrice(a);
        case "price_asc":
          return getPlayerPrice(a) - getPlayerPrice(b);
        case "form":
          return (
            (b.total_points_avg_last_3 ?? -100) -
            (a.total_points_avg_last_3 ?? -100)
          );
        case "value": {
          const va =
            (a.predicted_total_points ?? 0) / Math.max(getPlayerPrice(a), 0.1);
          const vb =
            (b.predicted_total_points ?? 0) / Math.max(getPlayerPrice(b), 0.1);
          return vb - va;
        }
        default:
          return 0;
      }
    });

    return list;
  }, [players, posTab, teamFilter, query, sortKey]);

  if (!open) return null;

  const title = replacingPlayer
    ? `Replace ${replacingPlayer.name ?? "Player"}`
    : targetPosition
      ? `Select ${normalizePosition(targetPosition) === "GKP" ? "Goalkeeper" : normalizePosition(targetPosition)}`
      : "Select Player";

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-[#0F172A]/50 backdrop-blur-xs"
          onClick={onClose}
          aria-hidden="true"
        />

        {/* Modal Window */}
        <motion.div
          role="dialog"
          aria-modal="true"
          initial={{ opacity: 0, scale: 0.96, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 12 }}
          transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
          className="relative z-10 flex h-[90vh] max-h-[820px] w-full max-w-3xl flex-col overflow-hidden rounded-chunky-xl border border-[#CBD5E1] bg-white text-[#0F172A] shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[#E2E8F0] bg-slate-900 px-5 py-4 text-white">
            <div className="flex items-center gap-2.5">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 text-white font-black">
                {replacingPlayer ? <RefreshCw size={16} /> : <Plus size={18} />}
              </div>
              <div>
                <h2 className="font-display text-base sm:text-lg font-black text-white leading-tight">
                  {title}
                </h2>
                <p className="text-[11px] font-medium text-slate-300">
                  {replacingPlayer
                    ? `Currently in squad for £${getPlayerPrice(replacingPlayer).toFixed(1)}m. Choose replacement.`
                    : "Select a player to add to your squad."}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              {/* Budget Badge */}
              <div className="rounded-lg bg-white/10 px-3 py-1 text-right text-xs font-black text-emerald-300 border border-white/10 hidden sm:block">
                <span className="text-[10px] font-bold text-slate-300 block uppercase">
                  Remaining Budget
                </span>
                <span>
                  £
                  {(
                    sq.remainingBudget +
                    (replacingPlayer ? getPlayerPrice(replacingPlayer) : 0)
                  ).toFixed(1)}
                  m
                </span>
              </div>

              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="rounded-full bg-white/10 p-2 text-white/80 transition-colors hover:bg-white/20 hover:text-white cursor-pointer"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Filters Bar */}
          <div className="flex flex-col gap-2.5 border-b border-[#E2E8F0] bg-[#F8FAFC] p-3 sm:p-4">
            {/* Position Tabs */}
            <div className="flex items-center gap-1 overflow-x-auto rounded-chunky border border-[#E2E8F0] bg-white p-1 shadow-xs">
              {POSITION_TABS.map((tab) => {
                const isActive = posTab === tab.id;
                return (
                  <button
                    key={tab.id}
                    type="button"
                    onClick={() => setPosTab(tab.id)}
                    className={cn(
                      "flex-1 rounded-xl px-3 py-1.5 text-center text-xs font-black transition-all cursor-pointer whitespace-nowrap",
                      isActive
                        ? "bg-[#10B981] text-white shadow-sm"
                        : "text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A]",
                    )}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>

            {/* Search + Dropdowns */}
            <div className="flex flex-wrap items-center gap-2">
              {/* Search Bar */}
              <div className="relative flex-1 min-w-[180px]">
                <Search
                  size={14}
                  className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search player or club…"
                  className="w-full rounded-xl border border-[#CBD5E1] bg-white py-2 pl-9 pr-3 text-xs font-bold text-slate-900 placeholder:text-slate-400 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 shadow-xs"
                />
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery("")}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>

              {/* Team Dropdown */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowTeamMenu((o) => !o)}
                  onBlur={() => setTimeout(() => setShowTeamMenu(false), 150)}
                  className="flex items-center gap-1.5 rounded-xl border border-[#CBD5E1] bg-white px-3 py-2 text-xs font-black text-slate-900 shadow-xs hover:border-slate-400 cursor-pointer"
                >
                  <span className="text-slate-500 font-bold">Club:</span>
                  <span className="font-black max-w-[90px] truncate">
                    {teamFilter === "all" ? "All" : teamFilter}
                  </span>
                  <ChevronDown size={12} className="text-slate-500" />
                </button>
                <AnimatePresence>
                  {showTeamMenu && (
                    <motion.ul
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="absolute right-0 top-full z-30 mt-1 max-h-56 w-48 overflow-y-auto rounded-chunky border border-[#E2E8F0] bg-white p-1 shadow-card"
                    >
                      {teamOptions.map((opt) => (
                        <li key={opt.value}>
                          <button
                            type="button"
                            onClick={() => {
                              setTeamFilter(opt.value);
                              setShowTeamMenu(false);
                            }}
                            className={cn(
                              "block w-full rounded-lg px-3 py-1.5 text-left text-xs font-black transition-colors cursor-pointer",
                              teamFilter === opt.value
                                ? "bg-emerald-50 text-emerald-700"
                                : "text-slate-700 hover:bg-slate-100",
                            )}
                          >
                            {opt.label}
                          </button>
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>
              </div>

              {/* Sort Dropdown */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowSortMenu((o) => !o)}
                  onBlur={() => setTimeout(() => setShowSortMenu(false), 150)}
                  className="flex items-center gap-1.5 rounded-xl border border-[#CBD5E1] bg-white px-3 py-2 text-xs font-black text-slate-900 shadow-xs hover:border-slate-400 cursor-pointer"
                >
                  <ArrowUpDown size={12} className="text-slate-500" />
                  <span className="font-black max-w-[110px] truncate">
                    {SORT_OPTIONS.find((o) => o.value === sortKey)?.label ?? "Sort"}
                  </span>
                  <ChevronDown size={12} className="text-slate-500" />
                </button>
                <AnimatePresence>
                  {showSortMenu && (
                    <motion.ul
                      initial={{ opacity: 0, y: -4 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -4 }}
                      className="absolute right-0 top-full z-30 mt-1 w-52 overflow-hidden rounded-chunky border border-[#E2E8F0] bg-white p-1 shadow-card"
                    >
                      {SORT_OPTIONS.map((opt) => (
                        <li key={opt.value}>
                          <button
                            type="button"
                            onClick={() => {
                              setSortKey(opt.value);
                              setShowSortMenu(false);
                            }}
                            className={cn(
                              "block w-full rounded-lg px-3 py-1.5 text-left text-xs font-black transition-colors cursor-pointer",
                              sortKey === opt.value
                                ? "bg-emerald-50 text-emerald-700"
                                : "text-slate-700 hover:bg-slate-100",
                            )}
                          >
                            {opt.label}
                          </button>
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </div>

          {/* Table Content */}
          <div className="flex-1 overflow-y-auto">
            {/* Table Header */}
            <div className="sticky top-0 z-10 grid grid-cols-[1fr_65px_65px_100px_70px] items-center gap-2 border-b border-[#E2E8F0] bg-[#F8FAFC] px-4 py-2.5 text-[10px] font-black uppercase tracking-wider text-slate-500 shadow-xs">
              <span>Player & Club</span>
              <span className="text-right">Price</span>
              <span className="text-right">AI xPts</span>
              <span className="text-center hidden sm:block">Fixtures</span>
              <span className="text-right">Action</span>
            </div>

            {/* Loading */}
            {loading && (
              <div className="flex flex-col gap-1.5 p-4">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-xl" />
                ))}
              </div>
            )}

            {/* Error */}
            {!loading && error && (
              <div className="p-6">
                <ErrorState message={error} onRetry={onRetry} />
              </div>
            )}

            {/* Empty State */}
            {!loading && !error && filteredPlayers.length === 0 && (
              <div className="p-8">
                <EmptyState
                  title="No players found"
                  description="Try adjusting your position, club or search filters."
                />
              </div>
            )}

            {/* Player List */}
            {!loading && !error && filteredPlayers.length > 0 && (
              <ul className="divide-y divide-slate-100">
                {filteredPlayers.map((p) => {
                  const inSquad = sq.isInSquad(p);

                  const check = replacingPlayer
                    ? sq.canReplacePlayer(replacingPlayer, p)
                    : sq.canAddPlayer(p, { targetPosition });

                  const eligible = check.allowed;
                  const isCurrentReplaceTarget =
                    replacingPlayer && getPlayerId(replacingPlayer) === getPlayerId(p);

                  const aiTag = getAITag(p.predicted_total_points);
                  const pos = normalizePosition(p.position);
                  const posLabel = pos === "GKP" ? "GK" : pos;

                  return (
                    <li
                      key={getPlayerId(p)}
                      className={cn(
                        "grid grid-cols-[1fr_65px_65px_100px_70px] items-center gap-2 px-4 py-2.5 transition-colors hover:bg-slate-50",
                        inSquad && !isCurrentReplaceTarget && "bg-emerald-50/40",
                        !eligible && "opacity-45 bg-slate-50/50",
                      )}
                    >
                      {/* Player Identity */}
                      <div className="flex items-center gap-2.5 min-w-0">
                        <PlayerAvatar
                          name={p.name}
                          photoUrl={p.photo_url}
                          size="sm"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5 truncate">
                            <span className="truncate text-xs font-black text-slate-900">
                              {p.name ?? "N/A"}
                            </span>
                            {aiTag && (
                              <span
                                className={cn(
                                  "shrink-0 rounded-full px-1.5 py-0.5 text-[8px] font-black uppercase leading-none hidden sm:inline-block",
                                  aiTag.tone === "emerald" &&
                                    "bg-emerald-100 text-emerald-800 border border-emerald-300",
                                  aiTag.tone === "gold" &&
                                    "bg-amber-100 text-amber-800 border border-amber-300",
                                  aiTag.tone === "sky" &&
                                    "bg-sky-100 text-sky-800 border border-sky-300",
                                )}
                              >
                                {aiTag.label}
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <TeamBadge
                              team={p.team}
                              logoUrl={p.team_logo_url}
                              size="sm"
                            />
                            <span className="rounded bg-slate-200 px-1 py-0.2 text-[9px] font-black text-slate-700 uppercase">
                              {posLabel}
                            </span>
                            {!eligible && check.reason && (
                              <span className="text-[10px] font-bold text-red-600 truncate flex items-center gap-0.5">
                                <AlertCircle size={10} className="shrink-0" />
                                {check.reason}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Price */}
                      <span className="numeral text-right text-xs font-black text-slate-800">
                        {formatPrice(p.value)}
                      </span>

                      {/* AI xPts as whole integer */}
                      <span className="numeral text-right text-xs font-black text-amber-900 bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 justify-self-end">
                        {formatInt(p.predicted_total_points)} xP
                      </span>

                      {/* Upcoming Fixtures */}
                      <div className="flex justify-center hidden sm:flex">
                        <UpcomingFixtures
                          player={p}
                          variant="inline"
                          maxFixtures={3}
                        />
                      </div>

                      {/* Select / Replace Action */}
                      <div className="flex justify-end">
                        <button
                          type="button"
                          disabled={!eligible}
                          onClick={() => {
                            if (!eligible) return;
                            onSelectPlayer(p);
                            onClose();
                          }}
                          className={cn(
                            "flex items-center justify-center gap-1 rounded-xl px-2.5 py-1.5 text-xs font-black shadow-xs transition-all cursor-pointer whitespace-nowrap",
                            eligible
                              ? replacingPlayer
                                ? "bg-sky-600 text-white hover:bg-sky-700 shadow-sm"
                                : "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm"
                              : "bg-slate-200 text-slate-400 cursor-not-allowed",
                          )}
                        >
                          {replacingPlayer ? (
                            <>
                              <RefreshCw size={12} />
                              <span className="hidden sm:inline">Replace</span>
                            </>
                          ) : (
                            <>
                              <Plus size={13} />
                              <span className="hidden sm:inline">Select</span>
                            </>
                          )}
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
