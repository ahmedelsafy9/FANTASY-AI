import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PlayerTokenProps {
  player: PlayerRecord;
  isCaptain?: boolean;
  onClick?: () => void;
  className?: string;
}

/**
 * Compact player representation for the pitch/squad formation view.
 * Shows a circular photo, short name, club badge, and predicted points.
 * Designed to fit inside formation grid slots on the Pitch component.
 */
export function PlayerToken({ player, isCaptain = false, onClick, className }: PlayerTokenProps) {
  const shortName = player.name
    ? player.name.length > 10
      ? player.name.split(/[.\s]/).pop() ?? player.name.slice(0, 10)
      : player.name
    : "N/A";

  return (
    <button
      onClick={onClick}
      className={cn(
        "group flex flex-col items-center gap-1 transition-transform duration-200",
        onClick && "hover:scale-105 active:scale-95",
        className,
      )}
    >
      <div className="relative">
        <PlayerAvatar
          name={player.name}
          photoUrl={player.photo_url}
          size="md"
          className={cn(
            "ring-2 ring-white/20 transition-all",
            isCaptain && "ring-gold ring-2",
            onClick && "group-hover:ring-emerald/50",
          )}
        />
        {isCaptain && (
          <div className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-gold text-[9px] font-bold text-void">
            C
          </div>
        )}
        <div className="absolute -bottom-0.5 left-1/2 -translate-x-1/2">
          <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" />
        </div>
      </div>
      <span className="mt-1 max-w-[80px] truncate text-center text-[11px] font-semibold text-white drop-shadow-md">
        {shortName}
      </span>
      <span className="numeral rounded-md bg-void/60 px-1.5 py-0.5 text-[10px] font-bold text-gold backdrop-blur-sm">
        {formatStat(player.predicted_total_points)}
      </span>
    </button>
  );
}

interface EmptySlotProps {
  label: string;
  className?: string;
}

/** Empty formation slot placeholder on the pitch. */
export function EmptySlot({ label, className }: EmptySlotProps) {
  return (
    <div className={cn("flex flex-col items-center gap-1", className)}>
      <div className="flex h-11 w-11 items-center justify-center rounded-full border-2 border-dashed border-white/20 bg-white/5">
        <span className="text-[10px] font-bold text-white/30">+</span>
      </div>
      <span className="text-[10px] text-white/30">{label}</span>
    </div>
  );
}
