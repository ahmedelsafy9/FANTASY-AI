import { X, Plus, ArrowUpDown } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { formatPrice, formatStat } from "@/lib/format";
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
  onClick?: () => void;
  onRemove?: () => void;
  onQuickSwap?: () => void;
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
  onClick,
  onRemove,
  onQuickSwap,
  className,
}: PlayerTokenProps) {
  const displayName = player.name
    ? player.name.length > 12
      ? player.name.split(/[.\s]/).pop() ?? player.name.slice(0, 10)
      : player.name
    : "N/A";

  const price = getRawPrice(player);

  return (
    <div
      className={cn(
        "group relative flex flex-col items-center gap-1 focus:outline-none cursor-pointer select-none transition-all duration-150",
        isInvalidSwapTarget && "opacity-40 grayscale pointer-events-auto cursor-not-allowed",
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
              ? "bg-emerald-600 text-white border border-emerald-500"
              : "bg-slate-900 text-white border border-slate-700",
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
          <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-30 rounded-full bg-emerald-500 px-2 py-0.5 text-[8px] font-black uppercase text-white shadow-md border border-white tracking-wider animate-pulse">
            SELECTED
          </div>
        )}

        <PlayerAvatar
          name={player.name}
          photoUrl={player.photo_url}
          size="md"
          className={cn(
            "ring-2 ring-white shadow-md transition-all",
            isSelected && "ring-emerald-400 ring-4 shadow-xl scale-105",
            isValidSwapTarget && "ring-amber-400 ring-3 shadow-glow-gold animate-pulse",
            isCaptain && !isSelected && "ring-amber-400 ring-4 shadow-glow-gold",
            isViceCaptain && !isSelected && "ring-sky-400 ring-4 shadow-glow",
            isFirstSub && !isSelected && "ring-emerald-500 ring-3",
            onClick && "group-hover/avatar:ring-emerald-400",
          )}
        />

        {/* Captain Badge (Top-Left) */}
        {isCaptain && !isSelected && (
          <div
            className="absolute -left-2 -top-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-amber-400 text-[11px] font-black text-slate-950 shadow-md border-2 border-white animate-bounce-sm"
            title="Captain (2x Points)"
          >
            C
          </div>
        )}

        {/* Vice Captain Badge (Top-Left if not captain) */}
        {!isCaptain && isViceCaptain && !isSelected && (
          <div
            className="absolute -left-2 -top-2 z-20 flex h-6 w-6 items-center justify-center rounded-full bg-sky-500 text-[10px] font-black text-white shadow-md border-2 border-white"
            title="Vice Captain"
          >
            VC
          </div>
        )}

        {/* Remove Button (Top-Right) - only show when not in active swap selection */}
        {onRemove && !isSelected && !isValidSwapTarget && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove();
            }}
            title={`Remove ${player.name ?? "player"} from squad`}
            className="absolute -right-2 -top-2 z-30 flex h-6 w-6 items-center justify-center rounded-full bg-red-600 text-white shadow-md border-2 border-white hover:bg-red-700 hover:scale-110 active:scale-90 transition-all cursor-pointer"
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
            className="absolute -bottom-2 left-1/2 -translate-x-1/2 z-30 flex items-center gap-0.5 rounded-full bg-emerald-600 px-2 py-0.5 text-[9px] font-black uppercase text-white shadow-lg border border-white hover:bg-emerald-500 hover:scale-110 active:scale-95 transition-all cursor-pointer"
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

      {/* Name Pill */}
      <button
        onClick={onClick}
        className={cn(
          "mt-0.5 max-w-[96px] truncate rounded bg-white px-2 py-0.5 text-center font-display text-[11px] font-black text-slate-900 shadow-sm border border-slate-200 transition-colors hover:bg-slate-50 cursor-pointer",
          isSelected && "bg-emerald-100 text-emerald-950 border-emerald-400 font-extrabold",
          isValidSwapTarget && "bg-amber-100 text-amber-950 border-amber-400 font-extrabold",
        )}
      >
        {displayName}
      </button>

      {/* Stats Bar (Price + AI Points) */}
      <div
        onClick={onClick}
        className="flex items-center gap-1.5 rounded-full border border-slate-800 bg-slate-950/95 px-2.5 py-0.5 shadow-md hover:bg-slate-900 transition-colors cursor-pointer"
      >
        <span className="numeral text-[9px] font-extrabold text-slate-300">
          {formatPrice(price)}
        </span>
        <span className="text-[9px] text-slate-600">•</span>
        <span className="numeral text-[10px] font-black text-amber-400">
          {formatStat(player.predicted_total_points)}
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
  className?: string;
}

export function EmptySlot({
  label,
  isHighlightTarget = false,
  targetBadgeLabel = "MOVE TO XI",
  onClick,
  className,
}: EmptySlotProps) {
  return (
    <button
      onClick={onClick}
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
          "relative flex h-14 w-14 sm:h-16 sm:w-16 items-center justify-center rounded-2xl border-2 border-dashed border-white/70 bg-white/20 backdrop-blur-xs shadow-md transition-all group-hover:border-emerald-400 group-hover:bg-emerald-500/30 group-hover:shadow-lg",
          isHighlightTarget &&
            "border-emerald-400 bg-emerald-500/40 shadow-glow ring-2 ring-emerald-400 animate-pulse",
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
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white shadow-sm border border-emerald-300 transition-transform group-hover:scale-110 group-hover:bg-emerald-400">
            <Plus size={14} strokeWidth={3} />
          </div>
        </div>
      </div>

      {/* Position Label Pill */}
      <span
        className={cn(
          "rounded-md bg-slate-900/90 px-2 py-0.5 font-display text-[10px] font-black uppercase text-white shadow-sm border border-slate-700/80 group-hover:bg-emerald-600 group-hover:border-emerald-500 transition-colors",
          isHighlightTarget && "bg-emerald-600 border-emerald-400 font-black animate-bounce",
        )}
      >
        {isHighlightTarget ? targetBadgeLabel : label}
      </span>
    </button>
  );
}
