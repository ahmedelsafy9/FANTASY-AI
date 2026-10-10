import { Crown, ChevronRight } from "lucide-react";
import type { MatchPrediction } from "@/types/api";
import { TeamBadge } from "@/components/identity";
import { Card } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

interface MatchCardProps {
  match: MatchPrediction;
  onClick: () => void;
}

function formatKickoff(dateStr?: string | null): string {
  if (!dateStr) return "TBD";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-GB", {
      weekday: "short",
      day: "numeric",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export function MatchCard({ match, onClick }: MatchCardProps) {
  const hwPct = Math.round(match.home_win_probability * 100);
  const drPct = Math.round(match.draw_probability * 100);
  const awPct = Math.round(match.away_win_probability * 100);

  // Normalization if rounding difference
  const total = hwPct + drPct + awPct;
  const hwWidth = total > 0 ? (hwPct / total) * 100 : 33.3;
  const drWidth = total > 0 ? (drPct / total) * 100 : 33.3;
  const awWidth = total > 0 ? (awPct / total) * 100 : 33.3;

  const resultTone =
    match.predicted_result === "HOME_WIN"
      ? { label: `${match.home_team} Win`, bg: "bg-[#EEE7FA] text-[#452477] border-[#D4C3ED]" }
      : match.predicted_result === "AWAY_WIN"
      ? { label: `${match.away_team} Win`, bg: "bg-[#EEF7FC] text-[#1E4D6B] border-[#B9DDF5]" }
      : { label: "Draw Predicted", bg: "bg-[#FDF8EC] text-[#8C680E] border-[#E5D08E]" };

  const confidenceTone =
    match.confidence_level === "HIGH"
      ? "bg-[#EEE7FA] text-[#452477] border-[#D4C3ED]"
      : match.confidence_level === "MODERATE"
      ? "bg-[#FDF8EC] text-[#8C680E] border-[#E5D08E]"
      : "bg-[#F4F3F6] text-[#6F6A76] border-[#E8E3ED]";

  return (
    <Card
      as="article"
      interactive
      className="group relative flex flex-col overflow-hidden border-[#E8E3ED] bg-white p-4 transition-all duration-200 hover:border-[#7041C5] hover:shadow-md"
      onClick={onClick}
    >
      {/* Top Bar: Gameweek, Kickoff & Confidence */}
      <div className="flex items-center justify-between pb-3 text-xs border-b border-[#E8E3ED]">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-[#F4F3F6] px-2 py-0.5 font-mono text-[11px] font-black text-[#19171D]">
            GW {match.gameweek}
          </span>
          <span className="font-semibold text-[#6F6A76]">
            {formatKickoff(match.kickoff_time)}
          </span>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wide",
              confidenceTone
            )}
          >
            {match.confidence_level} Confidence
          </span>
        </div>
      </div>

      {/* Main Clash Banner */}
      <div className="py-4">
        <div className="grid grid-cols-7 items-center gap-2">
          {/* Home Team */}
          <div className="col-span-3 flex flex-col items-center text-center sm:items-start sm:text-left">
            <div className="flex items-center gap-2 mb-1">
              <TeamBadge
                team={match.home_team}
                logoUrl={match.home_team_logo_url}
                size="md"
              />
              <span className="hidden font-display text-sm font-black text-[#19171D] sm:inline line-clamp-1">
                {match.home_team}
              </span>
            </div>
            <span className="font-display text-xs font-black text-[#19171D] sm:hidden truncate max-w-[80px]">
              {match.home_team}
            </span>
            <div className="mt-1 inline-flex items-center gap-1 rounded bg-[#F8F7FA] px-1.5 py-0.5 text-[10px] font-bold text-[#6F6A76] border border-[#E8E3ED]">
              <span>xG</span>
              <span className="font-mono font-black text-[#19171D]">
                {Math.round(match.predicted_home_goals)}
              </span>
            </div>
          </div>

          {/* Predicted Scoreline & Badge */}
          <div className="col-span-1 flex flex-col items-center justify-center text-center">
            <div className="font-display text-lg font-black tracking-tight text-[#19171D] sm:text-xl">
              {match.predicted_scoreline}
            </div>
            <span
              className={cn(
                "mt-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[9px] font-black uppercase leading-tight",
                resultTone.bg
              )}
            >
              {match.predicted_result.replace("_", " ")}
            </span>
          </div>

          {/* Away Team */}
          <div className="col-span-3 flex flex-col items-center text-center sm:items-end sm:text-right">
            <div className="flex items-center gap-2 mb-1 flex-row-reverse sm:flex-row">
              <span className="hidden font-display text-sm font-black text-[#19171D] sm:inline line-clamp-1">
                {match.away_team}
              </span>
              <TeamBadge
                team={match.away_team}
                logoUrl={match.away_team_logo_url}
                size="md"
              />
            </div>
            <span className="font-display text-xs font-black text-[#19171D] sm:hidden truncate max-w-[80px]">
              {match.away_team}
            </span>
            <div className="mt-1 inline-flex items-center gap-1 rounded bg-[#F8F7FA] px-1.5 py-0.5 text-[10px] font-bold text-[#6F6A76] border border-[#E8E3ED]">
              <span>xG</span>
              <span className="font-mono font-black text-[#19171D]">
                {Math.round(match.predicted_away_goals)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Segmented Win/Draw/Loss Probability Bar */}
      <div className="mt-1 space-y-1.5">
        <div className="flex justify-between text-[11px] font-bold text-[#19171D]">
          <span className="text-[#7041C5]">Home {hwPct}%</span>
          <span className="text-[#8C680E]">Draw {drPct}%</span>
          <span className="text-[#1E4D6B]">Away {awPct}%</span>
        </div>
        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-[#F4F3F6] p-0.5 border border-[#E8E3ED]">
          <div
            style={{ width: `${hwWidth}%` }}
            className="h-full rounded-l-full bg-[#7041C5] transition-all"
            title={`Home Win: ${hwPct}%`}
          />
          <div
            style={{ width: `${drWidth}%` }}
            className="h-full bg-[#B58A18] transition-all"
            title={`Draw: ${drPct}%`}
          />
          <div
            style={{ width: `${awWidth}%` }}
            className="h-full rounded-r-full bg-[#B9DDF5] transition-all"
            title={`Away Win: ${awPct}%`}
          />
        </div>
      </div>

      {/* Secondary Metrics / Fantasy Impact Quick Strip */}
      <div className="mt-3 pt-3 border-t border-[#E8E3ED] flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {match.best_captain_candidate && (
            <div className="inline-flex items-center gap-1 rounded-md bg-[#FDF8EC] px-2 py-0.5 text-[10px] font-bold text-[#8C680E] border border-[#E5D08E]">
              <Crown size={11} className="text-[#B58A18]" />
              <span className="truncate max-w-[120px]">
                {match.best_captain_candidate.name}
              </span>
              {match.best_captain_candidate.expected_points && (
                <span className="font-mono font-black text-[#8C680E]">
                  {Math.round(match.best_captain_candidate.expected_points)} xPts
                </span>
              )}
            </div>
          )}

          {typeof match.over_2_5_probability === "number" && (
            <span className="rounded bg-[#F8F7FA] px-1.5 py-0.5 text-[10px] font-bold text-[#6F6A76] border border-[#E8E3ED]">
              Over 2.5 goals: {Math.round(match.over_2_5_probability * 100)}%
            </span>
          )}

          {typeof match.btts_probability === "number" && (
            <span className="rounded bg-[#F8F7FA] px-1.5 py-0.5 text-[10px] font-bold text-[#6F6A76] border border-[#E8E3ED]">
              Both score: {Math.round(match.btts_probability * 100)}%
            </span>
          )}
        </div>

        <span className="inline-flex items-center text-xs font-bold text-[#7041C5] group-hover:translate-x-0.5 transition-transform">
          Details <ChevronRight size={14} />
        </span>
      </div>
    </Card>
  );
}
