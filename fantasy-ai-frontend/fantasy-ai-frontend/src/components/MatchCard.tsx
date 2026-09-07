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
      ? { label: `${match.home_team} Win`, bg: "bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]" }
      : match.predicted_result === "AWAY_WIN"
      ? { label: `${match.away_team} Win`, bg: "bg-[#EEF2FF] text-[#4F46E5] border-indigo-200" }
      : { label: "Draw Predicted", bg: "bg-[#FFFBEB] text-[#D97706] border-[#FDE68A]" };

  const confidenceTone =
    match.confidence_level === "HIGH"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : match.confidence_level === "MODERATE"
      ? "bg-amber-50 text-amber-700 border-amber-200"
      : "bg-slate-100 text-slate-600 border-slate-200";

  return (
    <Card
      as="article"
      interactive
      className="group relative flex flex-col overflow-hidden border-[#E2E8F0] p-4 transition-all duration-200 hover:border-[#10B981] hover:shadow-card-hover"
      onClick={onClick}
    >
      {/* Top Bar: Gameweek, Kickoff & Confidence */}
      <div className="flex items-center justify-between pb-3 text-xs border-b border-[#F1F5F9]">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-[#F1F5F9] px-2 py-0.5 font-mono text-[11px] font-black text-[#475569]">
            GW {match.gameweek}
          </span>
          <span className="font-semibold text-[#64748B]">
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
            {match.confidence_level} Conf ({Math.round(match.confidence * 100)}%)
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
              <span className="hidden font-display text-sm font-black text-[#0F172A] sm:inline line-clamp-1">
                {match.home_team}
              </span>
            </div>
            <span className="font-display text-xs font-black text-[#0F172A] sm:hidden truncate max-w-[80px]">
              {match.home_team}
            </span>
            <div className="mt-1 inline-flex items-center gap-1 rounded bg-[#F8FAFC] px-1.5 py-0.5 text-[10px] font-bold text-[#64748B] border border-[#E2E8F0]">
              <span>xG</span>
              <span className="font-mono font-black text-[#0F172A]">
                {match.predicted_home_goals.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Predicted Scoreline & Badge */}
          <div className="col-span-1 flex flex-col items-center justify-center text-center">
            <div className="font-display text-lg font-black tracking-tight text-[#0F172A] sm:text-xl">
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
              <span className="hidden font-display text-sm font-black text-[#0F172A] sm:inline line-clamp-1">
                {match.away_team}
              </span>
              <TeamBadge
                team={match.away_team}
                logoUrl={match.away_team_logo_url}
                size="md"
              />
            </div>
            <span className="font-display text-xs font-black text-[#0F172A] sm:hidden truncate max-w-[80px]">
              {match.away_team}
            </span>
            <div className="mt-1 inline-flex items-center gap-1 rounded bg-[#F8FAFC] px-1.5 py-0.5 text-[10px] font-bold text-[#64748B] border border-[#E2E8F0]">
              <span>xG</span>
              <span className="font-mono font-black text-[#0F172A]">
                {match.predicted_away_goals.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Segmented Win/Draw/Loss Probability Bar */}
      <div className="mt-1 space-y-1.5">
        <div className="flex justify-between text-[11px] font-bold text-[#475569]">
          <span className="text-[#059669]">Home {hwPct}%</span>
          <span className="text-[#D97706]">Draw {drPct}%</span>
          <span className="text-[#4F46E5]">Away {awPct}%</span>
        </div>
        <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-[#F1F5F9] p-0.5 border border-[#E2E8F0]">
          <div
            style={{ width: `${hwWidth}%` }}
            className="h-full rounded-l-full bg-[#10B981] transition-all"
            title={`Home Win: ${hwPct}%`}
          />
          <div
            style={{ width: `${drWidth}%` }}
            className="h-full bg-[#F59E0B] transition-all"
            title={`Draw: ${drPct}%`}
          />
          <div
            style={{ width: `${awWidth}%` }}
            className="h-full rounded-r-full bg-[#6366F1] transition-all"
            title={`Away Win: ${awPct}%`}
          />
        </div>
      </div>

      {/* Secondary Metrics / Fantasy Impact Quick Strip */}
      <div className="mt-3 pt-3 border-t border-[#F1F5F9] flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {match.best_captain_candidate && (
            <div className="inline-flex items-center gap-1 rounded-md bg-[#FFFBEB] px-2 py-0.5 text-[10px] font-bold text-[#92400E] border border-[#FDE68A]">
              <Crown size={11} className="text-[#F59E0B]" />
              <span className="truncate max-w-[120px]">
                {match.best_captain_candidate.name}
              </span>
              {match.best_captain_candidate.expected_points && (
                <span className="font-mono font-black text-[#B45309]">
                  {match.best_captain_candidate.expected_points.toFixed(1)} xPts
                </span>
              )}
            </div>
          )}

          {typeof match.over_2_5_probability === "number" && (
            <span className="rounded bg-[#F8FAFC] px-1.5 py-0.5 text-[10px] font-bold text-[#64748B] border border-[#E2E8F0]">
              O2.5: {Math.round(match.over_2_5_probability * 100)}%
            </span>
          )}

          {typeof match.btts_probability === "number" && (
            <span className="rounded bg-[#F8FAFC] px-1.5 py-0.5 text-[10px] font-bold text-[#64748B] border border-[#E2E8F0]">
              BTTS: {Math.round(match.btts_probability * 100)}%
            </span>
          )}
        </div>

        <span className="inline-flex items-center text-xs font-bold text-[#10B981] group-hover:translate-x-0.5 transition-transform">
          Details <ChevronRight size={14} />
        </span>
      </div>
    </Card>
  );
}
