import type { PlayerRecord } from "@/types/api";
import { TeamBadge } from "@/components/identity";
import { FDRBadge } from "@/components/FDRBadge";
import { getTeamCode } from "@/lib/format";
import { cn } from "@/lib/utils";

interface FixtureBadgeProps {
  player: PlayerRecord;
  size?: "sm" | "md" | "lg";
  className?: string;
}

export function FixtureBadge({ player, size = "sm", className }: FixtureBadgeProps) {
  const hasOpponent = Boolean(player.opponent_team);
  const isHome = player.is_home === 1;
  const isAway = player.is_home === 0;
  const opponentCode = getTeamCode(player.opponent_team);

  if (!hasOpponent) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] text-[#64748B] font-bold",
          size === "sm" ? "px-2.5 py-1.5 text-xs" : size === "md" ? "px-3 py-2 text-sm" : "px-4 py-3 text-sm",
          className,
        )}
      >
        <span>Fixture N/A</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-2.5 rounded-xl border border-[#E2E8F0] bg-white shadow-sm",
        size === "sm" ? "px-2.5 py-1.5" : size === "md" ? "px-3 py-2" : "px-4 py-3",
        className,
      )}
    >
      <TeamBadge
        team={player.opponent_team}
        logoUrl={player.opponent_logo_url}
        size={size === "lg" ? "md" : "sm"}
      />
      <div className="flex flex-col text-left">
        <span className={cn("font-display font-black text-[#0F172A] leading-none", size === "lg" ? "text-base" : "text-xs")}>
          {opponentCode}
        </span>
        <div className="flex items-center gap-1.5 mt-1">
          {(isHome || isAway) && (
            <span
              className={cn(
                "font-mono text-[10px] font-black uppercase",
                isHome ? "text-[#059669]" : "text-[#94A3B8]",
              )}
            >
              {isHome ? "HOME" : "AWAY"}
            </span>
          )}
          <FDRBadge difficulty={player.fixture_difficulty} size="sm" />
        </div>
      </div>
    </div>
  );
}
