import { useCallback, useMemo, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Crown,
  Plus,
  Shield,
  Users,
  Zap,
  RotateCcw,
  ChevronDown,
  AlertTriangle,
  X,
  ArrowUpDown,
  Trash2,
} from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import {
  useSquad,
  getPlayerId,
  getPlayerPrice,
  normalizePosition,
} from "@/hooks/useSquad";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { PlayerToken, EmptySlot } from "@/components/PlayerToken";
import { Pitch, PitchRow } from "@/components/Pitch";
import { Stat } from "@/components/stats";
import { Button, Badge, Skeleton } from "@/components/ui/primitives";
import { SearchInput } from "@/components/ui/SearchInput";
import { Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";
import { ErrorState, EmptyState } from "@/components/states";
import { formatPrice, formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

const POSITION_TABS = [
  { id: "all", label: "All" },
  { id: "GKP", label: "GK" },
  { id: "DEF", label: "DEF" },
  { id: "MID", label: "MID" },
  { id: "FWD", label: "FWD" },
] as const;

type SortKey = "prediction" | "price_asc" | "price_desc" | "form" | "value";

const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: "prediction", label: "AI Prediction" },
  { value: "price_desc", label: "Price (High)" },
  { value: "price_asc", label: "Price (Low)" },
  { value: "form", label: "Form" },
  { value: "value", label: "Best Value" },
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

export default function Squad() {
  const { data, loading, error, refetch } = usePredictions();
  const [query, setQuery] = useState("");
  const [posTab, setPosTab] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("prediction");
  const [teamFilter, setTeamFilter] = useState("all");
  const [showSortMenu, setShowSortMenu] = useState(false);
  const [showTeamMenu, setShowTeamMenu] = useState(false);
  const [detailPlayer, setDetailPlayer] = useState<PlayerRecord | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [swapSelectedPlayer, setSwapSelectedPlayer] = useState<PlayerRecord | null>(null);
  const [swapErrorMessage, setSwapErrorMessage] = useState<string | null>(null);

  const sq = useSquad();
  const players = data?.predictions ?? [];

  const teamOptions = useMemo(() => {
    const teams = Array.from(
      new Set(players.map((p) => p.team).filter(Boolean)),
    ) as string[];
    return [
      { value: "all", label: "All Teams" },
      ...teams.sort().map((t) => ({ value: t, label: t })),
    ];
  }, [players]);

  const filtered = useMemo(() => {
    let list = players.filter((p) => {
      if (posTab !== "all") {
        const norm = normalizePosition(p.position);
        if (posTab === "GKP" && norm !== "GKP") return false;
        if (posTab !== "GKP" && norm !== posTab) return false;
      }
      if (teamFilter !== "all" && p.team !== teamFilter) return false;
      if (query.trim()) {
        const q = query.toLowerCase();
        if (
          !p.name?.toLowerCase().includes(q) &&
          !p.team?.toLowerCase().includes(q)
        )
          return false;
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

  const handleTogglePlayer = useCallback(
    (player: PlayerRecord) => {
      if (sq.isInSquad(player)) {
        sq.removePlayer(player);
        if (
          swapSelectedPlayer &&
          getPlayerId(swapSelectedPlayer) === getPlayerId(player)
        ) {
          setSwapSelectedPlayer(null);
          setSwapErrorMessage(null);
        }
      } else {
        const check = sq.canAddPlayer(player);
        if (!check.allowed) return;
        sq.addPlayer(player);
      }
    },
    [sq, swapSelectedPlayer],
  );

  const handlePlayerTokenClick = useCallback(
    (player: PlayerRecord) => {
      const pid = getPlayerId(player);

      if (!swapSelectedPlayer) {
        setSwapSelectedPlayer(player);
        setSwapErrorMessage(null);
        return;
      }

      const selectedPid = getPlayerId(swapSelectedPlayer);
      if (selectedPid === pid) {
        setSwapSelectedPlayer(null);
        setSwapErrorMessage(null);
        return;
      }

      const res = sq.swapPlayers(swapSelectedPlayer, player);
      if (res.success) {
        setSwapSelectedPlayer(null);
        setSwapErrorMessage(null);
      } else {
        setSwapErrorMessage(res.reason ?? "Cannot swap these players.");
      }
    },
    [swapSelectedPlayer, sq],
  );

  const startGKP = sq.startingXI.filter(
    (p) => normalizePosition(p.position) === "GKP",
  );
  const startDEF = sq.startingXI.filter(
    (p) => normalizePosition(p.position) === "DEF",
  );
  const startMID = sq.startingXI.filter(
    (p) => normalizePosition(p.position) === "MID",
  );
  const startFWD = sq.startingXI.filter(
    (p) => normalizePosition(p.position) === "FWD",
  );

  const posCounts = sq.getPositionCounts(sq.squad);

  const posCountsInSquad: Record<string, number> = {
    GKP: posCounts.GKP || 0,
    DEF: posCounts.DEF || 0,
    MID: posCounts.MID || 0,
    FWD: posCounts.FWD || 0,
  };

  const posLimits: Record<string, number> = {
    GKP: 2,
    DEF: 5,
    MID: 5,
    FWD: 3,
  };

  const handleEmptySlotClick = useCallback(
    (posLabel: string) => {
      if (swapSelectedPlayer) {
        const isSub = sq.bench.some(
          (p) => getPlayerId(p) === getPlayerId(swapSelectedPlayer),
        );
        if (isSub) {
          const res = sq.movePlayerToStartingXI(swapSelectedPlayer);
          if (res.success) {
            setSwapSelectedPlayer(null);
            setSwapErrorMessage(null);
            return;
          } else {
            setSwapErrorMessage(
              res.reason ?? "Cannot move player to starting XI.",
            );
            return;
          }
        }
      }

      let targetTab = "all";
      if (posLabel.startsWith("GK")) targetTab = "GKP";
      else if (posLabel.startsWith("DEF")) targetTab = "DEF";
      else if (posLabel.startsWith("MID")) targetTab = "MID";
      else if (posLabel.startsWith("FWD")) targetTab = "FWD";
      else targetTab = "all";

      setPosTab(targetTab);

      const el = document.getElementById("player-selection-panel");
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },
    [swapSelectedPlayer, sq],
  );

  const emptyGK = Math.max(0, 1 - startGKP.length);
  const emptyDEF = Math.max(0, 4 - startDEF.length);
  const emptyMID = Math.max(0, 4 - startMID.length);
  const emptyFWD = Math.max(0, 2 - startFWD.length);

  const benchSlots: (PlayerRecord | null)[] = [
    ...sq.bench,
    ...Array(Math.max(0, 4 - sq.bench.length)).fill(null),
  ].slice(0, 4);

  return (
    <div className="mx-auto max-w-[1440px] px-4 py-6 pb-safe-bottom sm:px-6 lg:px-8">
      {/* SQUAD SUMMARY HEADER */}
      <div className="mb-6">
        <div className="mb-4 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] shadow-sm">
            <Shield size={20} />
          </div>
          <div>
            <h1 className="font-display text-2xl font-black text-[#0F172A] sm:text-3xl">
              Squad Selection
            </h1>
            <p className="text-sm font-semibold text-[#475569]">
              Build your 15-player squad. Machine learning powers every recommendation.
            </p>
          </div>
        </div>

        {/* Stats summary bar */}
        <div className="flex flex-wrap items-center gap-3 rounded-chunky-lg border border-[#E2E8F0] bg-white p-3.5 sm:gap-5 sm:p-4 shadow-card">
          <div className="flex items-center gap-2">
            <Users size={18} className="text-[#10B981]" />
            <Badge tone={sq.isFull ? "teal" : "neutral"}>
              {sq.squad.length}/{sq.maxSize}
            </Badge>
          </div>

          <div className="h-6 w-px bg-[#E2E8F0]" />

          {sq.squad.length > 0 && (
            <div className="flex flex-col">
              <span className="text-[10px] font-black uppercase tracking-wider text-[#64748B]">
                Formation
              </span>
              <span className="numeral text-sm font-black text-[#0F172A]">
                {sq.formationStr}
              </span>
            </div>
          )}

          <div className="h-6 w-px bg-[#E2E8F0] hidden sm:block" />

          <Stat
            label="Squad xPts"
            value={formatStat(sq.totalStartingXp)}
            tone="gold"
          />

          <div className="h-6 w-px bg-[#E2E8F0] hidden sm:block" />

          <Stat
            label="Total Value"
            value={`£${sq.totalSquadPrice.toFixed(1)}m`}
          />

          <div className="h-6 w-px bg-[#E2E8F0] hidden sm:block" />

          <Stat
            label="Remaining"
            value={`£${sq.remainingBudget.toFixed(1)}m`}
            tone={sq.remainingBudget < 0.5 && sq.squad.length > 0 ? "coral" : "teal"}
          />

          {sq.effectiveCaptain && (
            <>
              <div className="h-6 w-px bg-[#E2E8F0] hidden md:block" />
              <div className="hidden md:flex items-center gap-2">
                <Crown size={16} className="text-[#D97706]" />
                <span className="text-xs font-black text-[#0F172A]">
                  {sq.effectiveCaptain.name ?? "N/A"}{" "}
                  <span className="numeral text-[#D97706] font-black">
                    {formatStat(
                      (sq.effectiveCaptain.predicted_total_points ?? 0) * 2,
                    )}
                    <span className="text-[#64748B] text-[9px] ml-0.5 font-bold">
                      (2×)
                    </span>
                  </span>
                </span>
              </div>
            </>
          )}

          <div className="flex-1" />

          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={() => sq.autoPick(players)}
              disabled={players.length === 0}
              title="Auto Pick the best AI squad"
            >
              <Zap size={15} />
              <span className="hidden sm:inline">Auto Pick</span>
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                if (sq.squad.length === 0) return;
                setShowResetConfirm(true);
              }}
              disabled={sq.squad.length === 0}
            >
              <RotateCcw size={15} />
              <span className="hidden sm:inline">Reset</span>
            </Button>
          </div>
        </div>
      </div>

      {/* MAIN GRID */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[400px_1fr] xl:grid-cols-[440px_1fr]">
        {/* LEFT: Player Selection Panel */}
        <div id="player-selection-panel" className="order-2 lg:order-1 flex flex-col">
          {/* Position tabs */}
          <div className="mb-3 flex items-center gap-1 rounded-chunky border border-[#E2E8F0] bg-white p-1 shadow-sm">
            {POSITION_TABS.map((tab) => {
              const isActive = posTab === tab.id;
              const count =
                tab.id === "all"
                  ? sq.squad.length
                  : posCountsInSquad[tab.id] ?? 0;
              const limit =
                tab.id === "all" ? 15 : posLimits[tab.id] ?? 0;
              return (
                <button
                  key={tab.id}
                  onClick={() => setPosTab(tab.id)}
                  className={cn(
                    "relative flex-1 rounded-xl px-2 py-2 text-center text-xs font-black transition-all cursor-pointer",
                    isActive
                      ? "bg-[#10B981] text-white shadow-sm"
                      : "text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9]",
                  )}
                >
                  <span className="flex items-center justify-center gap-1">
                    {tab.label}
                    <span
                      className={cn(
                        "numeral text-[10px]",
                        isActive ? "text-white/90" : "text-[#64748B]",
                      )}
                    >
                      {count}/{limit}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>

          {/* Search + Filter row */}
          <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="flex-1">
              <SearchInput
                value={query}
                onChange={setQuery}
                placeholder="Search players…"
              />
            </div>

            {/* Team filter dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowTeamMenu((o) => !o)}
                onBlur={() =>
                  setTimeout(() => setShowTeamMenu(false), 120)
                }
                className="flex items-center gap-1.5 rounded-xl border border-[#CBD5E1] bg-white px-3 py-2 text-xs font-black text-[#0F172A] shadow-sm transition-colors hover:border-[#94A3B8] cursor-pointer"
              >
                <span className="text-[#64748B] font-bold">Team:</span>
                <span className="font-black max-w-[80px] truncate">
                  {teamFilter === "all" ? "All" : teamFilter}
                </span>
                <ChevronDown
                  size={12}
                  className={cn(
                    "transition-transform text-[#64748B]",
                    showTeamMenu && "rotate-180",
                  )}
                />
              </button>
              <AnimatePresence>
                {showTeamMenu && (
                  <motion.ul
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className="glass absolute right-0 top-full z-30 mt-1 max-h-60 w-48 overflow-y-auto rounded-chunky border border-[#E2E8F0] bg-white p-1 shadow-card"
                  >
                    {teamOptions.map((opt) => (
                      <li key={opt.value}>
                        <button
                          onClick={() => {
                            setTeamFilter(opt.value);
                            setShowTeamMenu(false);
                          }}
                          className={cn(
                            "block w-full rounded-lg px-3 py-1.5 text-left text-xs font-black transition-colors cursor-pointer",
                            teamFilter === opt.value
                              ? "bg-[#ECFDF5] text-[#059669]"
                              : "text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A]",
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

            {/* Sort dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowSortMenu((o) => !o)}
                onBlur={() =>
                  setTimeout(() => setShowSortMenu(false), 120)
                }
                className="flex items-center gap-1.5 rounded-xl border border-[#CBD5E1] bg-white px-3 py-2 text-xs font-black text-[#0F172A] shadow-sm transition-colors hover:border-[#94A3B8] cursor-pointer"
              >
                <ArrowUpDown size={12} className="text-[#64748B]" />
                <span className="font-black">
                  {SORT_OPTIONS.find((o) => o.value === sortKey)?.label ?? "Sort"}
                </span>
                <ChevronDown
                  size={12}
                  className={cn(
                    "transition-transform text-[#64748B]",
                    showSortMenu && "rotate-180",
                  )}
                />
              </button>
              <AnimatePresence>
                {showSortMenu && (
                  <motion.ul
                    initial={{ opacity: 0, y: -4 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -4 }}
                    transition={{ duration: 0.15 }}
                    className="glass absolute right-0 top-full z-30 mt-1 w-44 overflow-hidden rounded-chunky border border-[#E2E8F0] bg-white p-1 shadow-card"
                  >
                    {SORT_OPTIONS.map((opt) => (
                      <li key={opt.value}>
                        <button
                          onClick={() => {
                            setSortKey(opt.value);
                            setShowSortMenu(false);
                          }}
                          className={cn(
                            "block w-full rounded-lg px-3 py-1.5 text-left text-xs font-black transition-colors cursor-pointer",
                            sortKey === opt.value
                              ? "bg-[#ECFDF5] text-[#059669]"
                              : "text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A]",
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

          {/* Player table list */}
          <div className="flex-1 overflow-y-auto max-h-[calc(100vh-280px)] rounded-chunky-lg border border-[#E2E8F0] bg-white shadow-card">
            <div className="sticky top-0 z-10 grid grid-cols-[1fr_60px_60px_90px_40px] items-center gap-1 border-b border-[#E2E8F0] bg-[#F8FAFC] px-3.5 py-2.5 text-[10px] font-black uppercase tracking-wider text-[#64748B]">
              <span>Player</span>
              <span className="text-right">Price</span>
              <span className="text-right">xPts</span>
              <span className="text-center">Fixtures</span>
              <span />
            </div>

            {loading && (
              <div className="flex flex-col gap-1 p-3">
                {Array.from({ length: 8 }).map((_, i) => (
                  <Skeleton key={i} className="h-12 w-full rounded-lg" />
                ))}
              </div>
            )}

            {!loading && error && (
              <div className="p-4">
                <ErrorState message={error} onRetry={refetch} />
              </div>
            )}

            {!loading && !error && filtered.length === 0 && (
              <div className="p-4">
                <EmptyState title="No players match your filters" />
              </div>
            )}

            {!loading && !error && filtered.length > 0 && (
              <ul className="divide-y divide-[#E2E8F0]">
                {filtered.map((p) => {
                  const inSquad = sq.isInSquad(p);
                  const check = inSquad
                    ? { allowed: true }
                    : sq.canAddPlayer(p);
                  const disabled = !inSquad && !check.allowed;
                  const aiTag = getAITag(p.predicted_total_points);

                  return (
                    <li
                      key={getPlayerId(p)}
                      className={cn(
                        "grid grid-cols-[1fr_60px_60px_90px_40px] items-center gap-1 px-3.5 py-2.5 transition-colors",
                        inSquad
                          ? "bg-[#ECFDF5]"
                          : "hover:bg-[#F8FAFC]",
                        disabled && "opacity-40",
                      )}
                    >
                      {/* Player info */}
                      <button
                        className="flex items-center gap-2 min-w-0 text-left cursor-pointer"
                        onClick={() => setDetailPlayer(p)}
                        title="View player details"
                      >
                        <PlayerAvatar
                          name={p.name}
                          photoUrl={p.photo_url}
                          size="sm"
                        />
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-1.5">
                            <span className="truncate text-xs font-black text-[#0F172A]">
                              {p.name ?? "N/A"}
                            </span>
                            {aiTag && (
                              <span
                                className={cn(
                                  "shrink-0 rounded-full px-1.5 py-0.5 text-[8px] font-black uppercase leading-none",
                                  aiTag.tone === "emerald" &&
                                    "bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]",
                                  aiTag.tone === "gold" &&
                                    "bg-[#FFFBEB] text-[#92400E] border border-[#FDE68A]",
                                  aiTag.tone === "sky" &&
                                    "bg-[#F0F9FF] text-[#075985] border border-[#BAE6FD]",
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
                            {p.position && (
                              <span className="rounded bg-[#F1F5F9] px-1 py-0.5 text-[9px] font-black uppercase text-[#334155]">
                                {p.position === "GKP" ? "GK" : p.position}
                              </span>
                            )}
                          </div>
                        </div>
                      </button>

                      {/* Price */}
                      <span className="numeral text-right text-xs font-black text-[#334155]">
                        {formatPrice(p.value)}
                      </span>

                      {/* AI Predicted Points */}
                      <span className="numeral text-right text-xs font-black text-[#92400E] bg-[#FFFBEB] px-1.5 py-0.5 rounded border border-[#FDE68A]">
                        {formatStat(p.predicted_total_points)}
                      </span>

                      {/* Upcoming fixtures */}
                      <div className="flex justify-center">
                        <UpcomingFixtures
                          player={p}
                          variant="inline"
                          maxFixtures={3}
                          className="hidden sm:inline-flex"
                        />
                      </div>

                      {/* Add/Remove button */}
                      <div className="flex justify-end">
                        <button
                          onClick={() => handleTogglePlayer(p)}
                          disabled={disabled}
                          title={
                            inSquad
                              ? "Remove from squad"
                              : check.allowed
                                ? "Add to squad"
                                : check.reason ?? "Cannot add"
                          }
                          className={cn(
                            "flex h-7 w-7 items-center justify-center rounded-lg font-black transition-all cursor-pointer",
                            inSquad
                              ? "bg-[#FEF2F2] text-[#DC2626] hover:bg-[#FEE2E2] border border-[#FCA5A5]"
                              : check.allowed
                                ? "bg-[#10B981] text-white hover:bg-[#059669] shadow-sm"
                                : "bg-[#F1F5F9] text-[#94A3B8] cursor-not-allowed",
                          )}
                        >
                          {inSquad ? (
                            <X size={14} />
                          ) : (
                            <Plus size={14} />
                          )}
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>

        {/* RIGHT: Pitch + Bench */}
        <div className="order-1 lg:order-2 flex flex-col gap-4">
          {/* Floating Swap Action Bar */}
          <AnimatePresence>
            {swapSelectedPlayer && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="rounded-2xl border-2 border-[#10B981] bg-[#0F172A] p-3.5 text-white shadow-2xl backdrop-blur-md z-40"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2.5 min-w-0">
                    <PlayerAvatar
                      name={swapSelectedPlayer.name}
                      photoUrl={swapSelectedPlayer.photo_url}
                      size="sm"
                    />
                    <div className="min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-black truncate text-white">
                          {swapSelectedPlayer.name ?? "Player"}
                        </span>
                        <span className="rounded bg-[#10B981]/20 border border-[#10B981]/40 px-1.5 py-0.5 text-[9px] font-black uppercase text-[#34D399]">
                          {normalizePosition(swapSelectedPlayer.position)}
                        </span>
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[9px] font-bold text-slate-300">
                          {sq.startingXI.some(
                            (p) => getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                          )
                            ? "Starting XI"
                            : "Substitute"}
                        </span>
                      </div>
                      <p className="text-[11px] font-medium text-slate-300 truncate">
                        Select a player to swap with, or choose an action.
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {sq.startingXI.some(
                      (p) => getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                    ) ? (
                      <button
                        type="button"
                        onClick={() => {
                          const res = sq.movePlayerToBench(swapSelectedPlayer);
                          if (res.success) {
                            setSwapSelectedPlayer(null);
                            setSwapErrorMessage(null);
                          } else {
                            setSwapErrorMessage(
                              res.reason ?? "Cannot move player to bench."
                            );
                          }
                        }}
                        className="flex items-center gap-1.5 rounded-xl bg-[#10B981] px-3 py-1.5 text-xs font-black text-white hover:bg-[#059669] transition-colors cursor-pointer"
                      >
                        <ArrowUpDown size={13} />
                        <span>Move to Bench</span>
                      </button>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          const res = sq.movePlayerToStartingXI(swapSelectedPlayer);
                          if (res.success) {
                            setSwapSelectedPlayer(null);
                            setSwapErrorMessage(null);
                          } else {
                            setSwapErrorMessage(
                              res.reason ?? "Cannot move player to starting XI."
                            );
                          }
                        }}
                        className="flex items-center gap-1.5 rounded-xl bg-[#10B981] px-3 py-1.5 text-xs font-black text-white hover:bg-[#059669] transition-colors cursor-pointer"
                      >
                        <ArrowUpDown size={13} />
                        <span>Move to XI</span>
                      </button>
                    )}

                    <button
                      type="button"
                      onClick={() => {
                        setSwapSelectedPlayer(null);
                        setSwapErrorMessage(null);
                      }}
                      className="flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-black text-slate-300 hover:bg-slate-700 hover:text-white transition-colors cursor-pointer"
                    >
                      <X size={14} />
                      <span>Cancel</span>
                    </button>
                  </div>
                </div>

                {swapErrorMessage && (
                  <div className="mt-2.5 flex items-center gap-2 rounded-xl bg-red-500/20 border border-red-500/40 px-3 py-1.5 text-xs font-bold text-red-200">
                    <AlertTriangle size={14} className="shrink-0 text-red-400" />
                    <span>{swapErrorMessage}</span>
                  </div>
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {/* Pitch */}
          <Pitch className="min-h-[420px] sm:min-h-[480px]">
            {/* GK Row */}
            <PitchRow>
              {startGKP.map((p) => {
                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;

                return (
                  <PlayerToken
                    key={getPlayerId(p)}
                    player={p}
                    isCaptain={
                      sq.effectiveCaptain
                        ? getPlayerId(p) === getPlayerId(sq.effectiveCaptain)
                        : false
                    }
                    isViceCaptain={
                      sq.effectiveViceCaptain
                        ? getPlayerId(p) === getPlayerId(sq.effectiveViceCaptain)
                        : false
                    }
                    isSelected={isSelected}
                    isValidSwapTarget={isValidSwap}
                    isInvalidSwapTarget={isInvalidSwap}
                    onClick={() => handlePlayerTokenClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      const res = sq.swapPlayers(swapSelectedPlayer!, p);
                      if (res.success) {
                        setSwapSelectedPlayer(null);
                        setSwapErrorMessage(null);
                      } else {
                        setSwapErrorMessage(res.reason ?? "Cannot swap these players.");
                      }
                    }}
                  />
                );
              })}
              {Array.from({ length: emptyGK }).map((_, i) => {
                const isSubSelected = swapSelectedPlayer
                  ? sq.bench.some(
                      (p) => getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                    )
                  : false;
                const isGKSelected =
                  isSubSelected &&
                  normalizePosition(swapSelectedPlayer?.position) === "GKP";

                return (
                  <EmptySlot
                    key={`e-gk-${i}`}
                    label="GK"
                    isHighlightTarget={isGKSelected}
                    targetBadgeLabel="MOVE TO XI"
                    onClick={() => handleEmptySlotClick("GK")}
                  />
                );
              })}
            </PitchRow>

            {/* DEF Row */}
            <PitchRow>
              {startDEF.map((p) => {
                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;

                return (
                  <PlayerToken
                    key={getPlayerId(p)}
                    player={p}
                    isCaptain={
                      sq.effectiveCaptain
                        ? getPlayerId(p) === getPlayerId(sq.effectiveCaptain)
                        : false
                    }
                    isViceCaptain={
                      sq.effectiveViceCaptain
                        ? getPlayerId(p) === getPlayerId(sq.effectiveViceCaptain)
                        : false
                    }
                    isSelected={isSelected}
                    isValidSwapTarget={isValidSwap}
                    isInvalidSwapTarget={isInvalidSwap}
                    onClick={() => handlePlayerTokenClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      const res = sq.swapPlayers(swapSelectedPlayer!, p);
                      if (res.success) {
                        setSwapSelectedPlayer(null);
                        setSwapErrorMessage(null);
                      } else {
                        setSwapErrorMessage(res.reason ?? "Cannot swap these players.");
                      }
                    }}
                  />
                );
              })}
              {Array.from({ length: emptyDEF }).map((_, i) => {
                const isSubSelected = swapSelectedPlayer
                  ? sq.bench.some(
                      (p) => getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                    )
                  : false;
                const isDefSelected =
                  isSubSelected &&
                  normalizePosition(swapSelectedPlayer?.position) === "DEF";

                return (
                  <EmptySlot
                    key={`e-def-${i}`}
                    label="DEF"
                    isHighlightTarget={isDefSelected}
                    targetBadgeLabel="MOVE TO XI"
                    onClick={() => handleEmptySlotClick("DEF")}
                  />
                );
              })}
            </PitchRow>

            {/* MID Row */}
            <PitchRow>
              {startMID.map((p) => {
                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;

                return (
                  <PlayerToken
                    key={getPlayerId(p)}
                    player={p}
                    isCaptain={
                      sq.effectiveCaptain
                        ? getPlayerId(p) === getPlayerId(sq.effectiveCaptain)
                        : false
                    }
                    isViceCaptain={
                      sq.effectiveViceCaptain
                        ? getPlayerId(p) === getPlayerId(sq.effectiveViceCaptain)
                        : false
                    }
                    isSelected={isSelected}
                    isValidSwapTarget={isValidSwap}
                    isInvalidSwapTarget={isInvalidSwap}
                    onClick={() => handlePlayerTokenClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      const res = sq.swapPlayers(swapSelectedPlayer!, p);
                      if (res.success) {
                        setSwapSelectedPlayer(null);
                        setSwapErrorMessage(null);
                      } else {
                        setSwapErrorMessage(res.reason ?? "Cannot swap these players.");
                      }
                    }}
                  />
                );
              })}
              {Array.from({ length: emptyMID }).map((_, i) => {
                const isSubSelected = swapSelectedPlayer
                  ? sq.bench.some(
                      (p) => getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                    )
                  : false;
                const isMidSelected =
                  isSubSelected &&
                  normalizePosition(swapSelectedPlayer?.position) === "MID";

                return (
                  <EmptySlot
                    key={`e-mid-${i}`}
                    label="MID"
                    isHighlightTarget={isMidSelected}
                    targetBadgeLabel="MOVE TO XI"
                    onClick={() => handleEmptySlotClick("MID")}
                  />
                );
              })}
            </PitchRow>

            {/* FWD Row */}
            <PitchRow>
              {startFWD.map((p) => {
                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;

                return (
                  <PlayerToken
                    key={getPlayerId(p)}
                    player={p}
                    isCaptain={
                      sq.effectiveCaptain
                        ? getPlayerId(p) === getPlayerId(sq.effectiveCaptain)
                        : false
                    }
                    isViceCaptain={
                      sq.effectiveViceCaptain
                        ? getPlayerId(p) === getPlayerId(sq.effectiveViceCaptain)
                        : false
                    }
                    isSelected={isSelected}
                    isValidSwapTarget={isValidSwap}
                    isInvalidSwapTarget={isInvalidSwap}
                    onClick={() => handlePlayerTokenClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      const res = sq.swapPlayers(swapSelectedPlayer!, p);
                      if (res.success) {
                        setSwapSelectedPlayer(null);
                        setSwapErrorMessage(null);
                      } else {
                        setSwapErrorMessage(res.reason ?? "Cannot swap these players.");
                      }
                    }}
                  />
                );
              })}
              {Array.from({ length: emptyFWD }).map((_, i) => {
                const isSubSelected = swapSelectedPlayer
                  ? sq.bench.some(
                      (p) => getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                    )
                  : false;
                const isFwdSelected =
                  isSubSelected &&
                  normalizePosition(swapSelectedPlayer?.position) === "FWD";

                return (
                  <EmptySlot
                    key={`e-fwd-${i}`}
                    label="FWD"
                    isHighlightTarget={isFwdSelected}
                    targetBadgeLabel="MOVE TO XI"
                    onClick={() => handleEmptySlotClick("FWD")}
                  />
                );
              })}
            </PitchRow>
          </Pitch>

          {/* Substitutes */}
          <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-3.5 sm:p-4 shadow-card">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-xs font-black uppercase text-[#64748B]">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#64748B]" />
                Substitutes
              </h2>
              <span className="numeral text-xs font-black text-[#475569]">
                {sq.bench.length}/4
              </span>
            </div>

            <div className="grid grid-cols-4 gap-2 sm:gap-4">
              {benchSlots.map((p, idx) => {
                if (!p) {
                  const benchPosLabel = idx === 0 ? "GK" : "SUB";
                  return (
                    <div
                      key={`bench-empty-${idx}`}
                      className="flex flex-col items-center gap-1"
                    >
                      <EmptySlot
                        label={idx === 0 ? "GK" : `SUB ${idx}`}
                        onClick={() => handleEmptySlotClick(benchPosLabel)}
                      />
                    </div>
                  );
                }

                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;

                return (
                  <PlayerToken
                    key={getPlayerId(p)}
                    player={p}
                    benchLabel={idx === 0 ? "1st Sub" : `Sub ${idx + 1}`}
                    isFirstSub={idx === 0}
                    isSelected={isSelected}
                    isValidSwapTarget={isValidSwap}
                    isInvalidSwapTarget={isInvalidSwap}
                    onClick={() => handlePlayerTokenClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      const res = sq.swapPlayers(swapSelectedPlayer!, p);
                      if (res.success) {
                        setSwapSelectedPlayer(null);
                        setSwapErrorMessage(null);
                      } else {
                        setSwapErrorMessage(res.reason ?? "Cannot swap these players.");
                      }
                    }}
                  />
                );
              })}
            </div>
          </div>

          {/* Squad list summary sidebar */}
          {sq.squad.length > 0 && (
            <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-3.5 sm:p-4 shadow-card">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="flex items-center gap-2 text-xs font-black uppercase text-[#64748B]">
                  <Users size={14} className="text-[#10B981]" />
                  Your Squad Summary
                </h2>
                <div className="flex items-center gap-2">
                  <Badge tone={sq.isFull ? "teal" : "neutral"}>
                    {sq.squad.length}/{sq.maxSize}
                  </Badge>
                  <span className="numeral text-xs font-black text-[#92400E]">
                    {formatStat(sq.totalStartingXp)} xPts
                  </span>
                </div>
              </div>

              {/* Starting XI */}
              <div className="mb-3">
                <span className="text-[10px] font-black uppercase tracking-wider text-[#059669]">
                  Starting XI
                </span>
                <div className="mt-1 flex flex-col gap-0.5">
                  {sq.startingXI.map((p) => {
                    const isCap =
                      sq.effectiveCaptain &&
                      getPlayerId(p) ===
                        getPlayerId(sq.effectiveCaptain);
                    const isVC =
                      sq.effectiveViceCaptain &&
                      getPlayerId(p) ===
                        getPlayerId(sq.effectiveViceCaptain);
                    return (
                      <SquadListRow
                        key={getPlayerId(p)}
                        player={p}
                        isCaptain={!!isCap}
                        isViceCaptain={!!isVC}
                        onRemove={() => sq.removePlayer(p)}
                        onDetail={() => setDetailPlayer(p)}
                      />
                    );
                  })}
                </div>
              </div>

              {/* Bench */}
              {sq.bench.length > 0 && (
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider text-[#64748B]">
                    Bench
                  </span>
                  <div className="mt-1 flex flex-col gap-0.5">
                    {sq.bench.map((p, idx) => (
                      <SquadListRow
                        key={getPlayerId(p)}
                        player={p}
                        isFirstSub={idx === 0}
                        onRemove={() => sq.removePlayer(p)}
                        onDetail={() => setDetailPlayer(p)}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Player Detail Drawer */}
      <Drawer
        open={detailPlayer !== null}
        onClose={() => setDetailPlayer(null)}
      >
        {detailPlayer && (
          <div className="flex flex-col gap-4">
            <PlayerDetailPanel player={detailPlayer} />
            <div className="sticky bottom-0 bg-white pt-3 pb-1 border-t border-[#E2E8F0]">
              {sq.isInSquad(detailPlayer) ? (
                <Button
                  variant="secondary"
                  className="w-full !border-[#FCA5A5] !text-[#DC2626] hover:!bg-[#FEF2F2] font-black"
                  onClick={() => {
                    sq.removePlayer(detailPlayer);
                    setDetailPlayer(null);
                  }}
                >
                  <Trash2 size={15} />
                  Remove from Squad
                </Button>
              ) : (
                <Button
                  variant="primary"
                  className="w-full"
                  disabled={!sq.canAddPlayer(detailPlayer).allowed}
                  onClick={() => {
                    sq.addPlayer(detailPlayer);
                    setDetailPlayer(null);
                  }}
                >
                  <Plus size={15} />
                  {sq.canAddPlayer(detailPlayer).allowed
                    ? "Add to Squad"
                    : sq.canAddPlayer(detailPlayer).reason ?? "Cannot Add"}
                </Button>
              )}
            </div>
          </div>
        )}
      </Drawer>

      {/* Reset Modal */}
      <AnimatePresence>
        {showResetConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-[#0F172A]/40 backdrop-blur-sm"
              onClick={() => setShowResetConfirm(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="relative z-10 w-full max-w-sm rounded-chunky-xl border border-[#E2E8F0] bg-white p-6 shadow-card-hover"
            >
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FEF2F2] text-[#DC2626]">
                  <AlertTriangle size={20} />
                </div>
                <div>
                  <h3 className="font-display text-lg font-black text-[#0F172A]">
                    Reset Squad?
                  </h3>
                  <p className="text-sm font-bold text-[#475569]">
                    This will clear all {sq.squad.length} selected players.
                  </p>
                </div>
              </div>
              <div className="flex gap-3">
                <Button
                  variant="secondary"
                  className="flex-1"
                  onClick={() => setShowResetConfirm(false)}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  className="flex-1 !bg-[#DC2626] !border-[#B91C1C] hover:!bg-[#B91C1C]"
                  onClick={() => {
                    sq.resetSquad();
                    setShowResetConfirm(false);
                  }}
                >
                  Reset
                </Button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

function SquadListRow({
  player,
  isCaptain = false,
  isViceCaptain = false,
  isFirstSub = false,
  onRemove,
  onDetail,
}: {
  player: PlayerRecord;
  isCaptain?: boolean;
  isViceCaptain?: boolean;
  isFirstSub?: boolean;
  onRemove: () => void;
  onDetail: () => void;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      className={cn(
        "flex items-center gap-2 rounded-lg px-2 py-1.5 group transition-colors",
        isFirstSub && "border-l-2 border-[#10B981]",
        "hover:bg-[#F1F5F9]",
      )}
    >
      <button
        className="flex items-center gap-2 min-w-0 flex-1 cursor-pointer text-left"
        onClick={onDetail}
      >
        <PlayerAvatar
          name={player.name}
          photoUrl={player.photo_url}
          size="sm"
        />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1 truncate">
            <span className="truncate text-xs font-black text-[#0F172A]">
              {player.name ?? "N/A"}
            </span>
            {isCaptain && (
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#F59E0B] text-[9px] font-black text-[#0F172A] shrink-0">
                C
              </span>
            )}
            {isViceCaptain && (
              <span className="flex h-4 w-4 items-center justify-center rounded-full bg-[#0EA5E9] text-[9px] font-black text-white shrink-0">
                V
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            <TeamBadge
              team={player.team}
              logoUrl={player.team_logo_url}
              size="sm"
            />
            {player.position && (
              <span className="text-[9px] font-bold text-[#64748B]">
                {player.position === "GKP" ? "GK" : player.position}
              </span>
            )}
          </div>
        </div>
      </button>

      <span className="numeral text-[10px] font-bold text-[#475569] hidden sm:block">
        {formatPrice(player.value)}
      </span>

      <span className="numeral text-xs font-black text-[#92400E]">
        {formatStat(player.predicted_total_points)}
      </span>

      <button
        onClick={onRemove}
        aria-label={`Remove ${player.name ?? "player"}`}
        className="shrink-0 rounded-md p-1 text-[#64748B] opacity-0 group-hover:opacity-100 hover:bg-[#FEF2F2] hover:text-[#DC2626] transition-all cursor-pointer"
      >
        <Trash2 size={12} />
      </button>
    </motion.div>
  );
}
