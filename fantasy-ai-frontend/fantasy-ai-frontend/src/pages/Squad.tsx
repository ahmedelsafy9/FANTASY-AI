import React, { useCallback, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Crown,
  Shield,
  Users,
  Zap,
  RotateCcw,
  AlertTriangle,
  X,
  ArrowUpDown,
  ChevronDown,
  Sparkles,
  CheckCircle2,
} from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { usePredictions } from "@/hooks/useApi";
import {
  useSquad,
  getPlayerId,
  normalizePosition,
  SUPPORTED_FORMATIONS,
  parseFormation,
} from "@/hooks/useSquad";
import { PlayerToken, EmptySlot } from "@/components/PlayerToken";
import { Pitch, PitchRow } from "@/components/Pitch";
import { Stat } from "@/components/stats";
import { Button, Badge } from "@/components/ui/primitives";
import { Drawer } from "@/components/ui/overlays";
import { PlayerDetailPanel } from "@/components/PlayerDetailPanel";
import { PlayerActionModal } from "@/components/PlayerActionModal";
import { PlayerPickerModal } from "@/components/PlayerPickerModal";
import { formatPrice, formatInt } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function Squad() {
  const { data, loading, error, refetch } = usePredictions();
  const sq = useSquad();
  const players = data?.predictions ?? [];

  // Modal / Interaction states
  const [actionPlayer, setActionPlayer] = useState<PlayerRecord | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickerTargetPos, setPickerTargetPos] = useState<string | undefined>(undefined);
  const [replacingPlayer, setReplacingPlayer] = useState<PlayerRecord | null>(null);
  const [detailPlayer, setDetailPlayer] = useState<PlayerRecord | null>(null);
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showFormationMenu, setShowFormationMenu] = useState(false);

  // Swap mode state
  const [swapSelectedPlayer, setSwapSelectedPlayer] = useState<PlayerRecord | null>(null);
  const [swapErrorMessage, setSwapErrorMessage] = useState<string | null>(null);

  // Drag & Drop state
  const [draggingPlayer, setDraggingPlayer] = useState<PlayerRecord | null>(null);
  const [dragOverPlayerId, setDragOverPlayerId] = useState<string | null>(null);

  // Handle clicking a player card on pitch or bench
  const handlePlayerClick = useCallback(
    (player: PlayerRecord) => {
      // If currently in active swap mode:
      if (swapSelectedPlayer) {
        const selectedPid = getPlayerId(swapSelectedPlayer);
        const clickedPid = getPlayerId(player);

        if (selectedPid === clickedPid) {
          // Deselect swap
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
        return;
      }

      // Normal mode: open Player Action Modal (FPL style)
      setActionPlayer(player);
    },
    [swapSelectedPlayer, sq],
  );

  // Handle clicking an empty slot on pitch or bench
  const handleEmptySlotClick = useCallback(
    (posLabel: string) => {
      // If in swap mode and moving bench player to XI:
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
            setSwapErrorMessage(res.reason ?? "Cannot move player to Starting XI.");
            return;
          }
        }
      }

      // Open Player Picker for this position
      let targetPos: string | undefined = undefined;
      if (posLabel.startsWith("GK")) targetPos = "GKP";
      else if (posLabel.startsWith("DEF")) targetPos = "DEF";
      else if (posLabel.startsWith("MID")) targetPos = "MID";
      else if (posLabel.startsWith("FWD")) targetPos = "FWD";
      // If bench slot without explicit position, leave undefined so user can pick any needed outfield position

      setPickerTargetPos(targetPos);
      setReplacingPlayer(null);
      setPickerOpen(true);
    },
    [swapSelectedPlayer, sq],
  );

  // Drag & Drop handlers
  const handleDragStart = useCallback((_e: React.DragEvent, player: PlayerRecord) => {
    setDraggingPlayer(player);
    setSwapErrorMessage(null);
  }, []);

  const handleDragEnd = useCallback(() => {
    setDraggingPlayer(null);
    setDragOverPlayerId(null);
  }, []);

  const handleDragOverPlayer = useCallback((_e: React.DragEvent, targetPlayer: PlayerRecord) => {
    setDragOverPlayerId(getPlayerId(targetPlayer));
  }, []);

  const handleDropOnPlayer = useCallback(
    (_e: React.DragEvent, targetPlayer: PlayerRecord) => {
      if (!draggingPlayer) return;
      const srcPid = getPlayerId(draggingPlayer);
      const tgtPid = getPlayerId(targetPlayer);

      if (srcPid === tgtPid) {
        setDraggingPlayer(null);
        setDragOverPlayerId(null);
        return;
      }

      const res = sq.swapPlayers(draggingPlayer, targetPlayer);
      if (!res.success) {
        setSwapErrorMessage(res.reason ?? "Cannot swap these players.");
      } else {
        setSwapErrorMessage(null);
      }

      setDraggingPlayer(null);
      setDragOverPlayerId(null);
    },
    [draggingPlayer, sq],
  );

  // Open player picker for in-place replacement
  const handleOpenReplace = useCallback((player: PlayerRecord) => {
    setReplacingPlayer(player);
    setPickerTargetPos(normalizePosition(player.position));
    setPickerOpen(true);
  }, []);

  // Handle player selection from picker modal
  const handlePickerSelect = useCallback(
    (player: PlayerRecord) => {
      if (replacingPlayer) {
        sq.replacePlayer(replacingPlayer, player);
        setReplacingPlayer(null);
      } else {
        sq.addPlayer(player, { targetPosition: pickerTargetPos, asStarter: true });
      }
      setPickerOpen(false);
    },
    [replacingPlayer, pickerTargetPos, sq],
  );

  // Pitch rows mapped to active formation
  const formationStruct = parseFormation(sq.formation);

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

  const emptyGK = Math.max(0, 1 - startGKP.length);
  const emptyDEF = Math.max(0, formationStruct.def - startDEF.length);
  const emptyMID = Math.max(0, formationStruct.mid - startMID.length);
  const emptyFWD = Math.max(0, formationStruct.fwd - startFWD.length);

  // Bench slots:
  // Slot 0: Goalkeeper substitute (always the backup GK)
  // Slot 1, 2, 3: The 3 remaining outfield substitutes (DEF/MID/FWD depending on formation)
  const benchGkps = sq.bench.filter((p) => normalizePosition(p.position) === "GKP");
  const benchOutfield = sq.bench.filter((p) => normalizePosition(p.position) !== "GKP");

  const benchGkSlot: PlayerRecord | null = benchGkps[0] ?? null;
  const benchSub1: PlayerRecord | null = benchOutfield[0] ?? null;
  const benchSub2: PlayerRecord | null = benchOutfield[1] ?? null;
  const benchSub3: PlayerRecord | null = benchOutfield[2] ?? null;

  const benchSlots = [
    { player: benchGkSlot, label: "GK", isGk: true, posType: "GKP" },
    { player: benchSub1, label: "SUB 1", isGk: false, isFirstSub: true, posType: "OUTFIELD" },
    { player: benchSub2, label: "SUB 2", isGk: false, posType: "OUTFIELD" },
    { player: benchSub3, label: "SUB 3", isGk: false, posType: "OUTFIELD" },
  ];

  return (
    <div className="mx-auto max-w-[1400px] px-3 py-5 pb-safe-bottom sm:px-6 lg:px-8">
      {/* SQUAD BUILDER HEADER */}
      <div className="mb-5">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0] shadow-sm">
              <Shield size={20} />
            </div>
            <div>
              <h1 className="font-display text-2xl font-black text-[#0F172A] sm:text-3xl">
                Squad Builder
              </h1>
              <p className="text-xs font-semibold text-[#475569]">
                Assemble your 15-player squad (2 GK, 5 DEF, 5 MID, 3 FWD) with drag & drop flexibility.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              onClick={() => sq.autoPick(players)}
              disabled={players.length === 0}
              title="Auto Pick optimal AI starting XI & bench"
            >
              <Zap size={14} />
              <span>AI Auto Pick</span>
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
              <RotateCcw size={14} />
              <span>Reset</span>
            </Button>
          </div>
        </div>

        {/* STATS SUMMARY BAR */}
        <div className="flex flex-wrap items-center gap-2.5 rounded-chunky-lg border border-[#E2E8F0] bg-white p-3 sm:gap-4 sm:p-3.5 shadow-card">
          {/* Squad Count */}
          <div className="flex items-center gap-2">
            <Users size={16} className="text-[#10B981]" />
            <Badge tone={sq.isFull ? "teal" : "neutral"}>
              {sq.squad.length}/{sq.maxSize} Players
            </Badge>
          </div>

          <div className="h-5 w-px bg-[#E2E8F0]" />

          {/* Formation Selector Dropdown */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowFormationMenu((o) => !o)}
              onBlur={() => setTimeout(() => setShowFormationMenu(false), 150)}
              className="flex items-center gap-1.5 rounded-xl border border-[#CBD5E1] bg-[#F8FAFC] px-2.5 py-1 text-xs font-black text-[#0F172A] shadow-xs hover:border-[#10B981] transition-colors cursor-pointer"
            >
              <span className="text-[10px] font-bold uppercase text-[#64748B]">
                Formation:
              </span>
              <span className="font-black text-[#0F172A]">{sq.formation}</span>
              <ChevronDown
                size={12}
                className={cn(
                  "text-[#64748B] transition-transform",
                  showFormationMenu && "rotate-180",
                )}
              />
            </button>

            <AnimatePresence>
              {showFormationMenu && (
                <motion.ul
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -4 }}
                  className="absolute left-0 top-full z-40 mt-1 w-32 overflow-hidden rounded-chunky border border-[#E2E8F0] bg-white p-1 shadow-card"
                >
                  {SUPPORTED_FORMATIONS.map((f) => (
                    <li key={f}>
                      <button
                        type="button"
                        onClick={() => {
                          sq.setFormation(f);
                          setShowFormationMenu(false);
                        }}
                        className={cn(
                          "block w-full rounded-lg px-3 py-1.5 text-left text-xs font-black transition-colors cursor-pointer",
                          sq.formation === f
                            ? "bg-[#ECFDF5] text-[#059669]"
                            : "text-[#475569] hover:bg-[#F1F5F9] hover:text-[#0F172A]",
                        )}
                      >
                        {f}
                      </button>
                    </li>
                  ))}
                </motion.ul>
              )}
            </AnimatePresence>
          </div>

          <div className="h-5 w-px bg-[#E2E8F0] hidden sm:block" />

          {/* Starting xPts */}
          <Stat
            label="Starting xPts"
            value={`${formatInt(sq.totalStartingXp)}`}
            tone="gold"
          />

          <div className="h-5 w-px bg-[#E2E8F0] hidden sm:block" />

          {/* Total Value */}
          <Stat
            label="Squad Value"
            value={`£${sq.totalSquadPrice.toFixed(1)}m`}
          />

          <div className="h-5 w-px bg-[#E2E8F0] hidden sm:block" />

          {/* Remaining Budget */}
          <Stat
            label="Remaining Budget"
            value={`£${sq.remainingBudget.toFixed(1)}m`}
            tone={sq.remainingBudget < 0.5 && sq.squad.length > 0 ? "coral" : "teal"}
          />

          {/* Active Captain Callout */}
          {sq.effectiveCaptain && (
            <>
              <div className="h-5 w-px bg-[#E2E8F0] hidden md:block" />
              <div className="hidden md:flex items-center gap-2">
                <Crown size={15} className="text-[#D97706]" />
                <span className="text-xs font-black text-[#0F172A]">
                  Captain: {sq.effectiveCaptain.name ?? "N/A"}{" "}
                  <span className="numeral text-[#D97706] font-black">
                    {formatInt((sq.effectiveCaptain.predicted_total_points ?? 0) * 2)} xP
                    <span className="text-[#64748B] text-[9px] ml-0.5 font-bold">
                      (2×)
                    </span>
                  </span>
                </span>
              </div>
            </>
          )}
        </div>
      </div>

      {/* FLOATING ACTIVE SWAP / ERROR BANNER */}
      <AnimatePresence>
        {(swapSelectedPlayer || swapErrorMessage) && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="mb-4 rounded-2xl border-2 border-[#10B981] bg-[#0F172A] p-3.5 text-white shadow-xl z-30"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-500 text-white font-black">
                  <ArrowUpDown size={16} />
                </div>
                <div>
                  {swapSelectedPlayer ? (
                    <>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-black text-white">
                          Swap Mode: {swapSelectedPlayer.name}
                        </span>
                        <span className="rounded bg-emerald-500/20 border border-emerald-400/40 px-1.5 py-0.5 text-[9px] font-black uppercase text-emerald-300">
                          {normalizePosition(swapSelectedPlayer.position)}
                        </span>
                      </div>
                      <p className="text-[11px] font-medium text-slate-300">
                        Click or drag to another player to substitute.
                      </p>
                    </>
                  ) : (
                    <span className="text-xs font-black text-white">Notice</span>
                  )}
                </div>
              </div>

              <button
                type="button"
                onClick={() => {
                  setSwapSelectedPlayer(null);
                  setSwapErrorMessage(null);
                }}
                className="flex items-center gap-1 rounded-xl border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-black text-slate-300 hover:bg-slate-700 hover:text-white transition-colors cursor-pointer"
              >
                <X size={14} />
                <span>Dismiss</span>
              </button>
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

      {/* MAIN SQUAD BUILDER WORKSPACE */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px] xl:grid-cols-[1fr_380px]">
        {/* PITCH & BENCH AREA */}
        <div className="flex flex-col gap-4">
          {/* Pitch Container */}
          <Pitch className="min-h-[460px] sm:min-h-[540px]">
            {/* Formation Tag Pill on Pitch */}
            <div className="flex justify-center -mb-2">
              <span className="rounded-full bg-slate-900/80 backdrop-blur-xs px-3 py-0.5 text-[10px] font-black uppercase tracking-wider text-emerald-400 border border-emerald-500/40 shadow-sm">
                Active Formation • {sq.formation}
              </span>
            </div>

            {/* GOALKEEPER ROW */}
            <PitchRow>
              {startGKP.map((p) => {
                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : draggingPlayer
                    ? sq.canSwapPlayers(draggingPlayer, p)
                    : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;
                const isDragTgt = dragOverPlayerId === getPlayerId(p);

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
                    isDragging={draggingPlayer ? getPlayerId(draggingPlayer) === getPlayerId(p) : false}
                    isDragTarget={isDragTgt}
                    onDragStart={handleDragStart}
                    onDragEnd={handleDragEnd}
                    onDragOver={(e) => handleDragOverPlayer(e, p)}
                    onDrop={handleDropOnPlayer}
                    onClick={() => handlePlayerClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      if (swapSelectedPlayer) {
                        const res = sq.swapPlayers(swapSelectedPlayer, p);
                        if (res.success) {
                          setSwapSelectedPlayer(null);
                          setSwapErrorMessage(null);
                        } else {
                          setSwapErrorMessage(res.reason ?? "Cannot swap.");
                        }
                      }
                    }}
                  />
                );
              })}
              {Array.from({ length: emptyGK }).map((_, i) => (
                <EmptySlot
                  key={`e-gk-${i}`}
                  label="GK"
                  onClick={() => handleEmptySlotClick("GK")}
                />
              ))}
            </PitchRow>

            {/* DEFENDER ROW */}
            <PitchRow>
              {startDEF.map((p) => {
                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : draggingPlayer
                    ? sq.canSwapPlayers(draggingPlayer, p)
                    : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;
                const isDragTgt = dragOverPlayerId === getPlayerId(p);

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
                    isDragging={draggingPlayer ? getPlayerId(draggingPlayer) === getPlayerId(p) : false}
                    isDragTarget={isDragTgt}
                    onDragStart={handleDragStart}
                    onDragEnd={handleDragEnd}
                    onDragOver={(e) => handleDragOverPlayer(e, p)}
                    onDrop={handleDropOnPlayer}
                    onClick={() => handlePlayerClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      if (swapSelectedPlayer) {
                        const res = sq.swapPlayers(swapSelectedPlayer, p);
                        if (res.success) {
                          setSwapSelectedPlayer(null);
                          setSwapErrorMessage(null);
                        } else {
                          setSwapErrorMessage(res.reason ?? "Cannot swap.");
                        }
                      }
                    }}
                  />
                );
              })}
              {Array.from({ length: emptyDEF }).map((_, i) => (
                <EmptySlot
                  key={`e-def-${i}`}
                  label="DEF"
                  onClick={() => handleEmptySlotClick("DEF")}
                />
              ))}
            </PitchRow>

            {/* MIDFIELDER ROW */}
            <PitchRow>
              {startMID.map((p) => {
                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : draggingPlayer
                    ? sq.canSwapPlayers(draggingPlayer, p)
                    : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;
                const isDragTgt = dragOverPlayerId === getPlayerId(p);

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
                    isDragging={draggingPlayer ? getPlayerId(draggingPlayer) === getPlayerId(p) : false}
                    isDragTarget={isDragTgt}
                    onDragStart={handleDragStart}
                    onDragEnd={handleDragEnd}
                    onDragOver={(e) => handleDragOverPlayer(e, p)}
                    onDrop={handleDropOnPlayer}
                    onClick={() => handlePlayerClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      if (swapSelectedPlayer) {
                        const res = sq.swapPlayers(swapSelectedPlayer, p);
                        if (res.success) {
                          setSwapSelectedPlayer(null);
                          setSwapErrorMessage(null);
                        } else {
                          setSwapErrorMessage(res.reason ?? "Cannot swap.");
                        }
                      }
                    }}
                  />
                );
              })}
              {Array.from({ length: emptyMID }).map((_, i) => (
                <EmptySlot
                  key={`e-mid-${i}`}
                  label="MID"
                  onClick={() => handleEmptySlotClick("MID")}
                />
              ))}
            </PitchRow>

            {/* FORWARD ROW */}
            <PitchRow>
              {startFWD.map((p) => {
                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : draggingPlayer
                    ? sq.canSwapPlayers(draggingPlayer, p)
                    : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;
                const isDragTgt = dragOverPlayerId === getPlayerId(p);

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
                    isDragging={draggingPlayer ? getPlayerId(draggingPlayer) === getPlayerId(p) : false}
                    isDragTarget={isDragTgt}
                    onDragStart={handleDragStart}
                    onDragEnd={handleDragEnd}
                    onDragOver={(e) => handleDragOverPlayer(e, p)}
                    onDrop={handleDropOnPlayer}
                    onClick={() => handlePlayerClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      if (swapSelectedPlayer) {
                        const res = sq.swapPlayers(swapSelectedPlayer, p);
                        if (res.success) {
                          setSwapSelectedPlayer(null);
                          setSwapErrorMessage(null);
                        } else {
                          setSwapErrorMessage(res.reason ?? "Cannot swap.");
                        }
                      }
                    }}
                  />
                );
              })}
              {Array.from({ length: emptyFWD }).map((_, i) => (
                <EmptySlot
                  key={`e-fwd-${i}`}
                  label="FWD"
                  onClick={() => handleEmptySlotClick("FWD")}
                />
              ))}
            </PitchRow>
          </Pitch>

          {/* BENCH DUGOUT */}
          <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-card">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-xs font-black uppercase text-[#64748B]">
                <span className="inline-block h-2.5 w-2.5 rounded-full bg-[#64748B]" />
                Substitutes Bench (1 GK + 3 Outfield)
              </h2>
              <span className="numeral text-xs font-black text-[#475569]">
                {sq.bench.length}/4 Subs
              </span>
            </div>

            <div className="grid grid-cols-4 gap-2 sm:gap-4">
              {benchSlots.map((slot, idx) => {
                const p = slot.player;
                if (!p) {
                  return (
                    <div
                      key={`bench-empty-${idx}`}
                      className="flex flex-col items-center gap-1"
                    >
                      <EmptySlot
                        label={slot.label}
                        onClick={() => handleEmptySlotClick(slot.isGk ? "GK" : "")}
                      />
                    </div>
                  );
                }

                const isSelected = swapSelectedPlayer
                  ? getPlayerId(p) === getPlayerId(swapSelectedPlayer)
                  : false;
                const checkSwap = swapSelectedPlayer
                  ? sq.canSwapPlayers(swapSelectedPlayer, p)
                  : draggingPlayer
                    ? sq.canSwapPlayers(draggingPlayer, p)
                    : null;
                const isValidSwap = checkSwap ? checkSwap.allowed && !isSelected : false;
                const isInvalidSwap = checkSwap ? !checkSwap.allowed && !isSelected : false;
                const isDragTgt = dragOverPlayerId === getPlayerId(p);

                return (
                  <PlayerToken
                    key={getPlayerId(p)}
                    player={p}
                    benchLabel={slot.label}
                    isFirstSub={slot.isFirstSub}
                    isSelected={isSelected}
                    isValidSwapTarget={isValidSwap}
                    isInvalidSwapTarget={isInvalidSwap}
                    isDragging={draggingPlayer ? getPlayerId(draggingPlayer) === getPlayerId(p) : false}
                    isDragTarget={isDragTgt}
                    onDragStart={handleDragStart}
                    onDragEnd={handleDragEnd}
                    onDragOver={(e) => handleDragOverPlayer(e, p)}
                    onDrop={handleDropOnPlayer}
                    onClick={() => handlePlayerClick(p)}
                    onRemove={() => sq.removePlayer(p)}
                    onQuickSwap={() => {
                      if (swapSelectedPlayer) {
                        const res = sq.swapPlayers(swapSelectedPlayer, p);
                        if (res.success) {
                          setSwapSelectedPlayer(null);
                          setSwapErrorMessage(null);
                        } else {
                          setSwapErrorMessage(res.reason ?? "Cannot swap.");
                        }
                      }
                    }}
                  />
                );
              })}
            </div>
          </div>
        </div>

        {/* SIDEBAR: Squad Status & Player Quick-Actions */}
        <div className="flex flex-col gap-4">
          {/* SQUAD VALIDATION CARD */}
          <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-card">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="flex items-center gap-2 text-xs font-black uppercase text-[#64748B]">
                <Sparkles size={14} className="text-[#10B981]" />
                Squad Readiness
              </h2>
              {sq.isValidSquad ? (
                <span className="flex items-center gap-1 text-[11px] font-black text-emerald-600">
                  <CheckCircle2 size={13} />
                  Ready
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[11px] font-black text-amber-600">
                  <AlertTriangle size={13} />
                  In Progress
                </span>
              )}
            </div>

            {/* Validation items */}
            <div className="flex flex-col gap-2 text-xs font-bold text-slate-700">
              <div className="flex items-center justify-between">
                <span>Total Players:</span>
                <span
                  className={cn(
                    "numeral font-black",
                    sq.squad.length === 15 ? "text-emerald-600" : "text-amber-600",
                  )}
                >
                  {sq.squad.length}/15
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Starting XI:</span>
                <span
                  className={cn(
                    "numeral font-black",
                    sq.startingXI.length === 11 ? "text-emerald-600" : "text-amber-600",
                  )}
                >
                  {sq.startingXI.length}/11
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Captain Set:</span>
                <span
                  className={cn(
                    "font-black",
                    sq.effectiveCaptain ? "text-emerald-600" : "text-amber-600",
                  )}
                >
                  {sq.effectiveCaptain ? "Yes (C)" : "Missing"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Vice-Captain Set:</span>
                <span
                  className={cn(
                    "font-black",
                    sq.effectiveViceCaptain ? "text-emerald-600" : "text-amber-600",
                  )}
                >
                  {sq.effectiveViceCaptain ? "Yes (VC)" : "Missing"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>Budget Status:</span>
                <span
                  className={cn(
                    "numeral font-black",
                    sq.remainingBudget >= 0 ? "text-emerald-600" : "text-red-600",
                  )}
                >
                  £{sq.remainingBudget.toFixed(1)}m remaining
                </span>
              </div>
            </div>

            {/* Action buttons */}
            <div className="mt-4 flex flex-col gap-2">
              <Button
                variant="primary"
                className="w-full"
                onClick={() => {
                  setPickerTargetPos(undefined);
                  setReplacingPlayer(null);
                  setPickerOpen(true);
                }}
              >
                <span>Add / Browse Players</span>
              </Button>
            </div>
          </div>

          {/* SQUAD LIST BREAKDOWN */}
          {sq.squad.length > 0 && (
            <div className="rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-card">
              <h2 className="mb-2.5 text-xs font-black uppercase text-[#64748B]">
                Selected Players ({sq.squad.length})
              </h2>

              {/* Starters list */}
              <div className="mb-3">
                <span className="text-[10px] font-black uppercase tracking-wider text-emerald-700 block mb-1">
                  Starting XI ({sq.startingXI.length})
                </span>
                <div className="flex flex-col gap-1 max-h-56 overflow-y-auto">
                  {sq.startingXI.map((p) => {
                    const isCap =
                      sq.effectiveCaptain &&
                      getPlayerId(p) === getPlayerId(sq.effectiveCaptain);
                    const isVC =
                      sq.effectiveViceCaptain &&
                      getPlayerId(p) === getPlayerId(sq.effectiveViceCaptain);

                    return (
                      <div
                        key={getPlayerId(p)}
                        onClick={() => handlePlayerClick(p)}
                        className="flex items-center justify-between rounded-lg p-1.5 hover:bg-slate-50 transition-colors cursor-pointer border border-transparent hover:border-slate-200"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs font-black text-slate-900 truncate">
                            {p.name}
                          </span>
                          {isCap && (
                            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-amber-400 text-[9px] font-black text-slate-950">
                              C
                            </span>
                          )}
                          {isVC && (
                            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-sky-500 text-[9px] font-black text-white">
                              VC
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-[10px] font-bold text-slate-500">
                            {formatPrice(p.value)}
                          </span>
                          <span className="numeral text-xs font-black text-amber-800 bg-amber-50 px-1.5 py-0.5 rounded">
                            {formatInt(p.predicted_total_points)} xP
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Bench list */}
              {sq.bench.length > 0 && (
                <div>
                  <span className="text-[10px] font-black uppercase tracking-wider text-slate-500 block mb-1">
                    Bench ({sq.bench.length})
                  </span>
                  <div className="flex flex-col gap-1 max-h-40 overflow-y-auto">
                    {sq.bench.map((p, idx) => (
                      <div
                        key={getPlayerId(p)}
                        onClick={() => handlePlayerClick(p)}
                        className="flex items-center justify-between rounded-lg p-1.5 hover:bg-slate-50 transition-colors cursor-pointer border border-transparent hover:border-slate-200"
                      >
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-[10px] font-black uppercase text-slate-400">
                            {idx === 0 ? "GK" : `S${idx}`}
                          </span>
                          <span className="text-xs font-black text-slate-700 truncate">
                            {p.name}
                          </span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span className="text-[10px] font-bold text-slate-500">
                            {formatPrice(p.value)}
                          </span>
                          <span className="numeral text-xs font-black text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded">
                            {formatInt(p.predicted_total_points)} xP
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* PLAYER ACTION MODAL (FPL Card) */}
      <PlayerActionModal
        player={actionPlayer}
        isStarter={
          actionPlayer
            ? sq.startingXI.some((p) => getPlayerId(p) === getPlayerId(actionPlayer))
            : false
        }
        isCaptain={
          actionPlayer && sq.effectiveCaptain
            ? getPlayerId(actionPlayer) === getPlayerId(sq.effectiveCaptain)
            : false
        }
        isViceCaptain={
          actionPlayer && sq.effectiveViceCaptain
            ? getPlayerId(actionPlayer) === getPlayerId(sq.effectiveViceCaptain)
            : false
        }
        onClose={() => setActionPlayer(null)}
        onMakeCaptain={() => {
          if (actionPlayer) sq.setCaptain(actionPlayer);
        }}
        onMakeViceCaptain={() => {
          if (actionPlayer) sq.setViceCaptain(actionPlayer);
        }}
        onStartSwap={() => {
          if (actionPlayer) {
            setSwapSelectedPlayer(actionPlayer);
            setSwapErrorMessage(null);
          }
        }}
        onReplace={() => {
          if (actionPlayer) {
            handleOpenReplace(actionPlayer);
          }
        }}
        onViewDetails={() => {
          if (actionPlayer) setDetailPlayer(actionPlayer);
        }}
        onRemove={() => {
          if (actionPlayer) sq.removePlayer(actionPlayer);
        }}
      />

      {/* PLAYER PICKER MODAL / DRAWER */}
      <PlayerPickerModal
        open={pickerOpen}
        onClose={() => {
          setPickerOpen(false);
          setReplacingPlayer(null);
        }}
        targetPosition={pickerTargetPos}
        replacingPlayer={replacingPlayer}
        players={players}
        loading={loading}
        error={error}
        onRetry={refetch}
        sq={sq}
        onSelectPlayer={handlePickerSelect}
      />

      {/* FULL PLAYER DETAIL DRAWER */}
      <Drawer
        open={detailPlayer !== null}
        onClose={() => setDetailPlayer(null)}
      >
        {detailPlayer && (
          <div className="flex flex-col gap-4">
            <PlayerDetailPanel player={detailPlayer} />
          </div>
        )}
      </Drawer>

      {/* RESET SQUAD MODAL */}
      <AnimatePresence>
        {showResetConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-[#0F172A]/40 backdrop-blur-xs"
              onClick={() => setShowResetConfirm(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              className="relative z-10 w-full max-w-sm rounded-chunky-xl border border-[#E2E8F0] bg-white p-6 shadow-card-hover text-[#0F172A]"
            >
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#FEF2F2] text-[#DC2626]">
                  <AlertTriangle size={20} />
                </div>
                <div>
                  <h3 className="font-display text-lg font-black text-[#0F172A]">
                    Reset Squad?
                  </h3>
                  <p className="text-xs font-bold text-[#475569]">
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
