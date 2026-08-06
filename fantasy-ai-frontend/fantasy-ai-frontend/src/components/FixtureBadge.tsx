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

/**
 * A proper fixture block showing opponent badge, short code, home/away
 * indicator, and FDR badge. All fields rendered defensively — if no
 * opponent is available, shows an honest "N/A" state.
 */
export function FixtureBadge({ player, size = "sm", className }: FixtureBadgeProps) {
  const hasOpponent = Boolean(player.opponent_team);
  const isHome = player.is_home === 1;
  const isAway = player.is_home === 0;
  const opponentCode = getTeamCode(player.opponent_team);

  if (!hasOpponent) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 rounded-lg border border-border-soft bg-white/[0.03] text-ink-tertiary",
          size === "sm" ? "px-2.5 py-1.5 text-xs" : size === "md" ? "px-3 py-2 text-sm" : "px-4 py-3 text-sm",
          className,
        )}
      >
        <span className="text-ink-tertiary">Fixture N/A</span>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-2.5 rounded-lg border border-border-soft bg-white/[0.03]",
        size === "sm" ? "px-2.5 py-1.5" : size === "md" ? "px-3 py-2" : "px-4 py-3",
        className,
      )}
    >
      <TeamBadge
        team={player.opponent_team}
        logoUrl={player.opponent_logo_url}
        size={size === "lg" ? "md" : "sm"}
      />
      <div className="flex flex-col">
        <span className={cn("font-display font-semibold text-ink", size === "lg" ? "text-sm" : "text-xs")}>
          {opponentCode}
        </span>
        <div className="flex items-center gap-1.5">
          {(isHome || isAway) && (
            <span
              className={cn(
                "font-mono text-[10px] font-medium uppercase",
                isHome ? "text-emerald" : "text-ink-tertiary",
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
