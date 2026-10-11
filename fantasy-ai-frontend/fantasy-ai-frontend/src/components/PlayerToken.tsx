import React, { useState } from "react";
import { X, ArrowUpDown } from "lucide-react";
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

  const pointsVal = player.predicted_expected_points ?? player.predicted_total_points;

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
        isDragTarget && "scale-110 z-30 ring-4 ring-gold-metallic rounded-2xl shadow-glow-gold",
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
            "mb-0.5 rounded-full px-2.5 py-0.5 text-[9px] font-black uppercase tracking-wider shadow-xs z-10",
            isFirstSub
              ? "bg-gold-metallic text-stadium-dark border border-gold-border font-black"
              : "bg-stadium-deep text-ivory-surface border border-stadium-forest",
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
          <div className="absolute -top-3.5 left-1/2 -translate-x-1/2 z-30 rounded-full bg-stadium-deep px-2.5 py-0.5 text-[8px] font-black uppercase text-gold-bright shadow-lg border border-gold-border tracking-wider animate-pulse whitespace-nowrap">
            SELECTED
          </div>
        )}

        <PlayerAvatar
          name={player.name}
          photoUrl={player.photo_url}
          size="md"
          className={cn(
            "ring-2 ring-white shadow-md transition-all",
            isSelected && "ring-gold-metallic ring-4 shadow-xl scale-105",
            isValidSwapTarget && "ring-gold-metallic ring-3 shadow-glow-gold animate-pulse",
            isCaptain && !isSelected && "ring-gold-metallic ring-4 shadow-glow-gold",
            isViceCaptain && !isSelected && "ring-border ring-3 shadow-sm",
            isFirstSub && !isSelected && "ring-gold-muted ring-3",
            onClick && "group-hover/avatar:ring-gold-metallic",
          )}
        />

        {/* Captain Badge */}
        {isCaptain && !isSelected && (
          <div
            className="absolute -left-2 -top-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-gold-metallic text-[11px] font-black text-stadium-dark shadow-md border-2 border-white animate-bounce-sm"
            title="Captain (2× Points)"
          >
            C
          </div>
        )}

        {/* Vice Captain Badge */}
        {!isCaptain && isViceCaptain && !isSelected && (
          <div
            className="absolute -left-2 -top-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-ivory-surface text-[10px] font-black text-stadium-deep shadow-md border-2 border-stadium-forest"
            title="Vice Captain"
          >
            VC
          </div>
        )}

        {/* Remove Button */}
        {onRemove && !isSelected && !isValidSwapTarget && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            title={`Remove ${player.name ?? "player"} from squad`}
            className={cn(
              "absolute -right-2 -top-2 z-30 flex h-6 w-6 items-center justify-center rounded-full bg-rose-600 text-white shadow-md border-2 border-white hover:bg-rose-700 hover:scale-110 active:scale-90 transition-all cursor-pointer",
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
            className="absolute -bottom-2.5 left-1/2 -translate-x-1/2 z-30 flex items-center gap-0.5 rounded-full bg-gold-metallic px-2.5 py-0.5 text-[9px] font-black uppercase text-stadium-dark shadow-lg border border-white hover:bg-gold-bright hover:scale-110 active:scale-95 transition-all cursor-pointer whitespace-nowrap"
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
          "mt-0.5 max-w-[105px] truncate rounded-lg bg-ivory-surface px-2 py-0.5 text-center font-display text-[11px] font-black text-ink-primary shadow-xs border border-border transition-colors hover:bg-ivory-subtle cursor-pointer flex items-center justify-center gap-1",
          isSelected && "bg-stadium-deep text-ivory-surface border-stadium-forest font-extrabold",
          isValidSwapTarget && "bg-gold-light text-gold-dark border-gold-border font-extrabold",
        )}
      >
        <span className="truncate">{displayName}</span>
        <span className="text-[8px] font-bold text-ink-secondary shrink-0">({posLabel})</span>
      </button>

      {/* Stats Bar (Price + Expected Points strictly whole integer) */}
      <div
        onClick={onClick}
        className="flex items-center gap-1.5 rounded-full border border-gold-border/30 bg-stadium-dark/95 px-2.5 py-0.5 shadow-md hover:bg-stadium-deep transition-colors cursor-pointer"
      >
        <span className="numeral text-[9px] font-bold text-ivory-surface">
          {formatPrice(price)}
        </span>
        <span className="text-[9px] text-white/30">•</span>
        <span className="numeral text-[10px] font-black text-gold-bright">
          {formatInt(pointsVal)} xP
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
      className={cn(
        "group relative flex flex-col items-center justify-center gap-1 transition-all duration-150 select-none cursor-pointer",
        isHighlightTarget && "scale-105 z-20",
        className,
      )}
    >
      <div
        className={cn(
          "flex h-11 w-11 items-center justify-center rounded-full border-2 border-dashed transition-all",
          isHighlightTarget
            ? "border-gold-metallic bg-gold-light/40 text-gold-dark shadow-glow-gold animate-pulse scale-110"
            : "border-white/40 bg-black/25 text-white/80 hover:border-white/80 hover:bg-black/40",
        )}
      >
        <span className="text-[11px] font-mono font-black">{label}</span>
      </div>

      <span
        className={cn(
          "rounded-md px-2 py-0.5 text-[9px] font-mono font-black uppercase tracking-wider shadow-xs border transition-colors",
          isHighlightTarget
            ? "bg-gold-metallic text-stadium-dark border-gold-border animate-bounce-sm"
            : "bg-black/40 text-white/90 border-white/20",
        )}
      >
        {isHighlightTarget ? targetBadgeLabel : "+ Add"}
      </span>
    </button>
  );
}
