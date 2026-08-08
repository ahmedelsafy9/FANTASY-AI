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

export function UpcomingFixtures({
  player,
  fixtures,
  variant = "full",
  maxFixtures = 5,
  className,
}: UpcomingFixturesProps) {
  let rawList: UpcomingFixture[] = fixtures ?? player?.upcoming_fixtures ?? [];

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
          "inline-flex items-center rounded-lg border border-slate-300 bg-slate-100 px-2.5 py-1 text-xs font-bold text-slate-600",
          className,
        )}
      >
        No upcoming fixtures
      </div>
    );
  }

  // Inline variant (for tables & lists)
  if (variant === "inline") {
    return (
      <div className={cn("inline-flex items-center flex-wrap gap-1.5", className)}>
        {list.map((fix, idx) => {
          const code = fix.opponent_short_name || getTeamCode(fix.opponent_name);
          const isHome = fix.is_home;
          return (
            <span
              key={fix.fixture_id ?? `${fix.opponent_name}-${idx}`}
              className="inline-flex items-center gap-1 rounded-md border border-slate-300 bg-slate-100 px-2 py-0.5 font-mono text-[11px] shadow-sm"
            >
              <span className="font-black text-slate-900">{code}</span>
              <span className={isHome ? "text-emerald-700 font-black" : "text-slate-600 font-bold"}>
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
              className="flex shrink-0 items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-2.5 py-1 shadow-sm"
            >
              <TeamBadge
                team={fix.opponent_name}
                logoUrl={fix.opponent_logo_url}
                size="sm"
              />
              <div className="flex flex-col">
                <span className="font-display text-[11px] font-black leading-none text-slate-900">
                  {code}
                </span>
                <span
                  className={cn(
                    "font-mono text-[9px] leading-none uppercase mt-0.5 font-black",
                    fix.is_home ? "text-emerald-700" : "text-slate-600",
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

  // Full variant
  return (
    <div className={cn("flex items-center gap-3 overflow-x-auto no-scrollbar pb-1", className)}>
      {list.map((fix, idx) => {
        const code = fix.opponent_short_name || getTeamCode(fix.opponent_name);
        const kickoffDate = formatKickoffDate(fix.kickoff_time);

        return (
          <div
            key={fix.fixture_id ?? `${fix.opponent_name}-${idx}`}
            className="flex shrink-0 min-w-[130px] flex-col gap-2 rounded-chunky-lg border border-slate-200 bg-white p-3.5 shadow-card transition-all hover:border-emerald-400"
          >
            <div className="flex items-center justify-between text-[10px] font-black text-slate-500">
              <span>{typeof fix.event === "number" ? `GW ${fix.event}` : "GW -"}</span>
              <span
                className={cn(
                  "font-mono font-black uppercase text-[9px]",
                  fix.is_home ? "text-emerald-700" : "text-slate-600",
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
                <span className="font-display text-xs font-black text-slate-900 truncate" title={fix.opponent_name}>
                  {code}
                </span>
                {kickoffDate && (
                  <span className="text-[10px] text-slate-600 font-bold truncate">{kickoffDate}</span>
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
