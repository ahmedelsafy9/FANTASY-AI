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
  onClick?: () => void;
  className?: string;
}

export function PlayerToken({
  player,
  isCaptain = false,
  isViceCaptain = false,
  benchLabel,
  isFirstSub = false,
  onClick,
  className,
}: PlayerTokenProps) {
  const displayName = player.name
    ? player.name.length > 12
      ? player.name.split(/[.\s]/).pop() ?? player.name.slice(0, 10)
      : player.name
    : "N/A";

  const price = getRawPrice(player);

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative flex flex-col items-center gap-1 transition-all duration-150 focus:outline-none cursor-pointer",
        onClick && "hover:scale-105 active:scale-95",
        className,
      )}
    >
      {/* Bench Order Label */}
      {benchLabel && (
        <span
          className={cn(
            "mb-0.5 rounded-full px-2.5 py-0.5 text-[9px] font-black uppercase tracking-wider shadow-sm",
            isFirstSub
              ? "bg-emerald-600 text-white border border-emerald-700"
              : "bg-slate-900 text-white border border-slate-700",
          )}
        >
          {benchLabel}
        </span>
      )}

      {/* Avatar Container */}
      <div className="relative">
        <PlayerAvatar
          name={player.name}
          photoUrl={player.photo_url}
          size="md"
          className={cn(
            "ring-2 ring-white shadow-card transition-all",
            isCaptain && "ring-amber-400 ring-4 shadow-glow-gold",
            isViceCaptain && "ring-sky-400 ring-4 shadow-glow",
            isFirstSub && "ring-emerald-500 ring-3",
            onClick && "group-hover:ring-emerald-400",
          )}
        />

        {/* Captain Badge */}
        {isCaptain && (
          <div
            className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-amber-400 text-[11px] font-black text-slate-950 shadow-md border-2 border-white animate-bounce-sm"
            title="Captain (2x Points)"
          >
            C
          </div>
        )}

        {/* Vice Captain Badge */}
        {!isCaptain && isViceCaptain && (
          <div
            className="absolute -right-2 -top-2 flex h-6 w-6 items-center justify-center rounded-full bg-sky-500 text-[10px] font-black text-white shadow-md border-2 border-white"
            title="Vice Captain"
          >
            VC
          </div>
        )}

        {/* Team Badge */}
        <div className="absolute -bottom-1 left-1/2 -translate-x-1/2">
          <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" />
        </div>
      </div>

      {/* Name Pill */}
      <span className="mt-0.5 max-w-[95px] truncate text-center font-display text-[11px] font-black text-white drop-shadow-[0_1px_3px_rgba(0,0,0,0.9)]">
        {displayName}
      </span>

      {/* Stats Bar (Price + AI Points) */}
      <div className="flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-900/95 px-2.5 py-0.5 shadow-md">
        <span className="numeral text-[9px] font-extrabold text-slate-200">
          {formatPrice(price)}
        </span>
        <span className="text-[9px] text-slate-500">•</span>
        <span className="numeral text-[10px] font-black text-amber-400">
          {formatStat(player.predicted_total_points)}
        </span>
      </div>
    </button>
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
  onClick?: () => void;
  className?: string;
}

export function EmptySlot({ label, onClick, className }: EmptySlotProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex flex-col items-center gap-1 transition-all group focus:outline-none cursor-pointer",
        onClick && "hover:scale-105",
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full border-2 border-dashed border-white/60 bg-white/20 transition-colors group-hover:border-emerald-400 group-hover:bg-emerald-500/30 shadow-sm">
        <span className="text-sm font-black text-white group-hover:text-white">+</span>
      </div>
      <span className="text-[10px] font-black text-white drop-shadow-[0_1px_2px_rgba(0,0,0,0.8)]">
        {label}
      </span>
    </button>
  );
}
