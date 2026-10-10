import React, { useState } from "react";
import { X, Plus, ArrowUpDown } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { formatPrice, formatInt } from "@/lib/format";
import { normalizePosition } from "@/hooks/useSquad";
import { cn } from "@/lib/utils";

interface PlayerTokenProps {
  player: PlayerRecord;
  isCaptain?: boolean;
  isViceCaptain?: boolean;
  benchLabel?: string;
  isFirstSub?: boolean;
  isSelected?: boolean;
  isValidSwapTarget?: boolean;
  isInvalidSwapTarget?: boolean;
  isDragging?: boolean;
  isDragTarget?: boolean;
  onClick?: () => void;
  onRemove?: () => void;
  onQuickSwap?: () => void;
  onDragStart?: (e: React.DragEvent, player: PlayerRecord) => void;
  onDragEnd?: (e: React.DragEvent) => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDragLeave?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent, targetPlayer: PlayerRecord) => void;
  className?: string;
}

export function PlayerToken({
  player,
  isCaptain = false,
  isViceCaptain = false,
  benchLabel,
  isFirstSub = false,
  isSelected = false,
  isValidSwapTarget = false,
  isInvalidSwapTarget = false,
  isDragging = false,
  isDragTarget = false,
  onClick,
  onRemove,
  onQuickSwap,
  onDragStart,
  onDragEnd,
  onDragOver,
  onDragLeave,
  onDrop,
  className,
}: PlayerTokenProps) {
  const [isHovered, setIsHovered] = useState(false);

  const displayName = player.name
    ? player.name.length > 12
      ? player.name.split(/[.\s]/).pop() ?? player.name.slice(0, 10)
      : player.name
    : "N/A";

  const price = getRawPrice(player);
  const pos = normalizePosition(player.position);
  const posLabel = pos === "GKP" ? "GK" : pos;

  return (
    <div
      draggable={!isInvalidSwapTarget}
      onDragStart={(e) => {
        if (onDragStart) {
          onDragStart(e, player);
        }
      }}
      onDragEnd={onDragEnd}
      onDragOver={(e) => {
        e.preventDefault();
        if (onDragOver) onDragOver(e);
      }}
      onDragLeave={onDragLeave}
      onDrop={(e) => {
        e.preventDefault();
        if (onDrop) onDrop(e, player);
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      className={cn(
        "group relative flex flex-col items-center gap-1 focus:outline-none cursor-grab active:cursor-grabbing select-none transition-all duration-150",
        isDragging && "opacity-40 scale-95",
        isDragTarget && "scale-110 z-30 ring-4 ring-amber-400 rounded-2xl shadow-glow-gold",
        isInvalidSwapTarget && "opacity-35 grayscale pointer-events-auto cursor-not-allowed",
        isSelected && "z-30 scale-105",
        isValidSwapTarget && "z-20",
        className,
      )}
    >
      {/* Bench Order Label */}
      {benchLabel && (
        <span
          className={cn(
            "mb-0.5 rounded-full px-2.5 py-0.5 text-[9px] font-black uppercase tracking-wider shadow-sm z-10",
            isFirstSub
              ? "bg-[#7041C5] text-white border border-[#8C60DF]"
              : "bg-[#19171D] text-white border border-[#2D2A32]",
          )}
        >
          {benchLabel}
        </span>
      )}

      {/* Avatar Container */}
      <div
        onClick={onClick}
        className="relative group/avatar cursor-pointer transition-transform duration-150 active:scale-95 group-hover:scale-105"
      >
        {/* Selected Badge */}
        {isSelected && (
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-30 rounded-full bg-[#7041C5] px-2 py-0.5 text-[8px] font-black uppercase text-white shadow-md border border-white tracking-wider animate-pulse whitespace-nowrap">
            SELECTED
          </div>
        )}

        <PlayerAvatar
          name={player.name}
          photoUrl={player.photo_url}
          size="md"
          className={cn(
            "ring-2 ring-white shadow-md transition-all",
            isSelected && "ring-[#7041C5] ring-4 shadow-xl scale-105",
            isValidSwapTarget && "ring-[#B58A18] ring-3 shadow-glow-gold animate-pulse",
            isCaptain && !isSelected && "ring-[#B58A18] ring-4 shadow-glow-gold",
            isViceCaptain && !isSelected && "ring-[#B9DDF5] ring-4 shadow-glow",
            isFirstSub && !isSelected && "ring-[#7041C5] ring-3",
            onClick && "group-hover/avatar:ring-[#7041C5]",
          )}
        />

        {/* Captain Badge (Top-Left) */}
        {isCaptain && !isSelected && (
          <div
            className="absolute -left-2 -top-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-[#B58A18] text-[11px] font-black text-white shadow-md border-2 border-white animate-bounce-sm"
            title="Captain (2× Points)"
          >
            C
          </div>
        )}

        {/* Vice Captain Badge (Top-Left if not captain) */}
        {!isCaptain && isViceCaptain && !isSelected && (
          <div
            className="absolute -left-2 -top-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-[#B9DDF5] text-[10px] font-black text-[#19171D] shadow-md border-2 border-white"
            title="Vice Captain"
          >
            VC
          </div>
        )}

        {/* Remove Button (Top-Right) */}
        {onRemove && !isSelected && !isValidSwapTarget && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            title={`Remove ${player.name ?? "player"} from squad`}
            className={cn(
              "absolute -right-2 -top-2 z-30 flex h-6 w-6 items-center justify-center rounded-full bg-[#EF4444] text-white shadow-md border-2 border-white hover:bg-red-700 hover:scale-110 active:scale-90 transition-all cursor-pointer",
              isHovered ? "opacity-100" : "opacity-0 sm:opacity-0",
            )}
          >
            <X size={13} strokeWidth={3} />
          </button>
        )}

        {/* SWAP Target Action Overlay Badge */}
        {isValidSwapTarget && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              if (onQuickSwap) onQuickSwap();
              else if (onClick) onClick();
            }}
            className="absolute -bottom-2 left-1/2 -translate-x-1/2 z-30 flex items-center gap-0.5 rounded-full bg-[#7041C5] px-2 py-0.5 text-[9px] font-black uppercase text-white shadow-lg border border-white hover:bg-[#5D32A8] hover:scale-110 active:scale-95 transition-all cursor-pointer whitespace-nowrap"
            title="Click to swap with selected player"
          >
            <ArrowUpDown size={10} strokeWidth={3} />
            <span>SWAP</span>
          </button>
        )}

        {/* Team Badge */}
        {!isValidSwapTarget && (
          <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 z-10">
            <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" />
          </div>
        )}
      </div>

      {/* Name Pill with Position Chip */}
      <button
        type="button"
        onClick={onClick}
        className={cn(
          "mt-0.5 max-w-[100px] truncate rounded bg-white px-2 py-0.5 text-center font-display text-[11px] font-black text-[#19171D] shadow-sm border border-[#E8E3ED] transition-colors hover:bg-[#F8F7FA] cursor-pointer flex items-center justify-center gap-1",
          isSelected && "bg-[#EEE7FA] text-[#452477] border-[#D4C3ED] font-extrabold",
          isValidSwapTarget && "bg-[#FDF8EC] text-[#8C680E] border-[#E5D08E] font-extrabold",
        )}
      >
        <span className="truncate">{displayName}</span>
        <span className="text-[8px] font-bold text-[#6F6A76] shrink-0">({posLabel})</span>
      </button>

      {/* Stats Bar (Price + AI Points as whole integer) */}
      <div
        onClick={onClick}
        className="flex items-center gap-1.5 rounded-full border border-black/30 bg-[#19171D]/90 px-2.5 py-0.5 shadow-md hover:bg-[#19171D] transition-colors cursor-pointer"
      >
        <span className="numeral text-[9px] font-extrabold text-[#EEE7FA]">
          {formatPrice(price)}
        </span>
        <span className="text-[9px] text-white/40">•</span>
        <span className="numeral text-[10px] font-black text-[#B58A18]">
          {formatInt(player.predicted_total_points)} xP
        </span>
      </div>
    </div>
  );
}

function getRawPrice(player: PlayerRecord): number {
  const raw = player.value ?? player.now_cost;
  const val = typeof raw === "number" ? raw : Number(raw);
  if (val === null || val === undefined || Number.isNaN(val)) return 0;
  return val;
}

interface EmptySlotProps {
  label: string;
  isHighlightTarget?: boolean;
  targetBadgeLabel?: string;
  onClick?: () => void;
  onDragOver?: (e: React.DragEvent) => void;
  onDragLeave?: (e: React.DragEvent) => void;
  onDrop?: (e: React.DragEvent) => void;
  className?: string;
}

export function EmptySlot({
  label,
  isHighlightTarget = false,
  targetBadgeLabel = "MOVE HERE",
  onClick,
  onDragOver,
  onDragLeave,
  onDrop,
  className,
}: EmptySlotProps) {
  return (
    <button
      onClick={onClick}
      onDragOver={(e) => {
        e.preventDefault();
        if (onDragOver) onDragOver(e);
      }}
      onDragLeave={onDragLeave}
      onDrop={(e) => {
        e.preventDefault();
        if (onDrop) onDrop(e);
      }}
      type="button"
      title={`Click to select a ${label} player`}
      className={cn(
        "group relative flex flex-col items-center justify-center gap-1 focus:outline-none cursor-pointer transition-all duration-150 select-none",
        onClick && "hover:scale-105 active:scale-95",
        isHighlightTarget && "scale-105 z-20",
        className,
      )}
    >
      {/* FPL Empty Shirt Silhouette Container */}
      <div
        className={cn(
          "relative flex h-14 w-14 sm:h-16 sm:w-16 items-center justify-center rounded-2xl border-2 border-dashed border-white/70 bg-white/20 backdrop-blur-xs shadow-md transition-all group-hover:border-[#EEE7FA] group-hover:bg-[#7041C5]/30 group-hover:shadow-lg",
          isHighlightTarget &&
            "border-[#EEE7FA] bg-[#7041C5]/40 shadow-glow ring-2 ring-[#7041C5] animate-pulse",
        )}
      >
        {/* FPL Jersey Silhouette Icon */}
        <svg
          viewBox="0 0 64 64"
          fill="none"
          stroke="currentColor"
          className="h-10 w-10 text-white/50 transition-colors group-hover:text-white/90"
          aria-hidden="true"
        >
          <path
            d="M 18 10 L 26 14 C 28 16 36 16 38 14 L 46 10 L 60 22 L 50 30 L 46 26 L 46 56 L 18 56 L 18 26 L 14 30 L 4 22 Z"
            fill="currentColor"
            fillOpacity="0.2"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinejoin="round"
          />
        </svg>

        {/* Embedded + Button */}
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[#7041C5] text-white shadow-sm border border-[#8C60DF] transition-transform group-hover:scale-110 group-hover:bg-[#5D32A8]">
            <Plus size={14} strokeWidth={3} />
          </div>
        </div>
      </div>

      {/* Position Label Pill */}
      <span
        className={cn(
          "rounded-md bg-[#19171D]/90 px-2 py-0.5 font-display text-[10px] font-black uppercase text-white shadow-sm border border-[#2D2A32] group-hover:bg-[#7041C5] group-hover:border-[#8C60DF] transition-colors",
          isHighlightTarget && "bg-[#7041C5] border-[#8C60DF] font-black animate-bounce",
        )}
      >
        {isHighlightTarget ? targetBadgeLabel : label}
      </span>
    </button>
  );
}
