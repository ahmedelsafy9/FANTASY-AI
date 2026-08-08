import type { PlayerRecord, UpcomingFixture } from "@/types/api";
import { TeamBadge } from "@/components/identity";
import { FDRBadge } from "@/components/FDRBadge";
import { getTeamCode } from "@/lib/format";
import { cn } from "@/lib/utils";

interface UpcomingFixturesProps {
  player?: PlayerRecord;
  fixtures?: UpcomingFixture[] | null;
  variant?: "full" | "compact" | "inline";
  maxFixtures?: number;
  className?: string;
}

/** Formats ISO kickoff time into a short date string (e.g., "21 Aug") */
function formatKickoffDate(isoString?: string | null): string | null {
  if (!isoString) return null;
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  } catch {
    return null;
  }
}

/**
 * Reusable UpcomingFixtures component displaying a sequence of upcoming matches
 * for a player or team, supporting full, compact, and inline representations.
 */
export function UpcomingFixtures({
  player,
  fixtures,
  variant = "full",
  maxFixtures = 5,
  className,
}: UpcomingFixturesProps) {
  // Extract upcoming_fixtures list from prop or player record
  let rawList: UpcomingFixture[] = fixtures ?? player?.upcoming_fixtures ?? [];

  // Fallback to legacy single fixture if upcoming_fixtures list is empty
  if (rawList.length === 0 && player?.opponent_team) {
    rawList = [
      {
        fixture_id: 0,
        event: player.predicted_for_gw,
        is_home: player.is_home === 1,
        opponent_team_id: 0,
        opponent_name: player.opponent_team,
        opponent_short_name: getTeamCode(player.opponent_team),
        opponent_logo_url: player.opponent_logo_url,
        difficulty: player.fixture_difficulty,
      },
    ];
  }

  const list = rawList.slice(0, maxFixtures);

  if (list.length === 0) {
    return (
      <div
        className={cn(
          "inline-flex items-center rounded-lg border border-border-soft bg-white/[0.03] px-2.5 py-1 text-xs text-ink-tertiary",
          className,
        )}
      >
        No upcoming fixtures
      </div>
    );
  }

  // Inline variant (ultra-compact for tables & browser lists)
  if (variant === "inline") {
    return (
      <div className={cn("inline-flex items-center flex-wrap gap-1.5", className)}>
        {list.map((fix, idx) => {
          const code = fix.opponent_short_name || getTeamCode(fix.opponent_name);
          const isHome = fix.is_home;
          return (
            <span
              key={fix.fixture_id ?? `${fix.opponent_name}-${idx}`}
              className="inline-flex items-center gap-1 rounded bg-white/5 px-1.5 py-0.5 font-mono text-[11px]"
            >
              <span className="font-semibold text-ink">{code}</span>
              <span className={isHome ? "text-emerald font-semibold" : "text-ink-tertiary"}>
                {isHome ? "H" : "A"}
              </span>
              <FDRBadge difficulty={fix.difficulty} size="sm" />
            </span>
          );
        })}
      </div>
    );
  }

  // Compact variant (used in PlayerCard)
  if (variant === "compact") {
    return (
      <div className={cn("flex items-center gap-2 overflow-x-auto no-scrollbar py-0.5", className)}>
        {list.map((fix, idx) => {
          const code = fix.opponent_short_name || getTeamCode(fix.opponent_name);
          return (
            <div
              key={fix.fixture_id ?? `${fix.opponent_name}-${idx}`}
              className="flex shrink-0 items-center gap-1.5 rounded-md border border-border-soft bg-surface-elevated/40 px-2 py-1"
            >
              <TeamBadge
                team={fix.opponent_name}
                logoUrl={fix.opponent_logo_url}
                size="sm"
              />
              <div className="flex flex-col">
                <span className="font-display text-[11px] font-semibold leading-none text-ink">
                  {code}
                </span>
                <span
                  className={cn(
                    "font-mono text-[9px] leading-none uppercase mt-0.5",
                    fix.is_home ? "text-emerald font-semibold" : "text-ink-tertiary",
                  )}
                >
                  {fix.is_home ? "HOME" : "AWAY"}
                </span>
              </div>
              <FDRBadge difficulty={fix.difficulty} size="sm" />
            </div>
          );
        })}
      </div>
    );
  }

  // Full variant (used in PlayerDetailPanel, modal, and dedicated fixture cards)
  return (
    <div className={cn("flex items-center gap-3 overflow-x-auto no-scrollbar pb-1", className)}>
      {list.map((fix, idx) => {
        const code = fix.opponent_short_name || getTeamCode(fix.opponent_name);
        const kickoffDate = formatKickoffDate(fix.kickoff_time);

        return (
          <div
            key={fix.fixture_id ?? `${fix.opponent_name}-${idx}`}
            className="flex shrink-0 min-w-[125px] flex-col gap-2 rounded-xl border border-border-soft bg-surface-elevated/60 p-3 transition-all hover:border-emerald/20"
          >
            <div className="flex items-center justify-between text-[10px] font-medium text-ink-tertiary">
              <span>{typeof fix.event === "number" ? `GW ${fix.event}` : "GW -"}</span>
              <span
                className={cn(
                  "font-mono font-semibold uppercase text-[9px]",
                  fix.is_home ? "text-emerald" : "text-ink-tertiary",
                )}
              >
                {fix.is_home ? "HOME" : "AWAY"}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <TeamBadge
                team={fix.opponent_name}
                logoUrl={fix.opponent_logo_url}
                size="md"
              />
              <div className="flex flex-col min-w-0">
                <span className="font-display text-xs font-bold text-ink truncate" title={fix.opponent_name}>
                  {code}
                </span>
                {kickoffDate && (
                  <span className="text-[9px] text-ink-tertiary truncate">{kickoffDate}</span>
                )}
              </div>
            </div>

            <div className="mt-0.5 flex items-center justify-between">
              <FDRBadge difficulty={fix.difficulty} size="sm" showLabel={false} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
