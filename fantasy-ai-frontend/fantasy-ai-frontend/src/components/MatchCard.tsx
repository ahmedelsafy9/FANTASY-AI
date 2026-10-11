import { Crown, ChevronRight, Calendar } from "lucide-react";
import type { MatchPrediction } from "@/types/api";
import { TeamBadge } from "@/components/identity";
import { OutcomeProbabilityBar } from "@/components/OutcomeProbabilityBar";
import { cn } from "@/lib/utils";

interface MatchCardProps {
  match: MatchPrediction;
  onClick: () => void;
}

function formatKickoff(dateStr?: string | null): string {
  if (!dateStr) return "Fixture Date TBD";
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
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
  const confidenceTone =
    match.confidence_level === "HIGH"
      ? "bg-stadium-surface/10 text-stadium-deep border-stadium-forest/30"
      : match.confidence_level === "MODERATE"
      ? "bg-gold-light text-gold-dark border-gold-border"
      : "bg-ivory-subtle text-ink-secondary border-border";

  return (
    <article
      className="group relative flex flex-col justify-between overflow-hidden rounded-2xl border border-border bg-ivory-surface p-5 text-ink-primary shadow-card transition-all duration-300 hover:-translate-y-1 hover:border-gold-border hover:shadow-card-hover cursor-pointer"
      onClick={onClick}
    >
      {/* Top Bar: Gameweek, Kickoff & Model Confidence */}
      <div className="flex items-center justify-between pb-3.5 border-b border-border/70 text-xs">
        <div className="flex items-center gap-2">
          <span className="rounded-md bg-stadium-deep text-ivory-surface px-2.5 py-0.5 font-mono text-[11px] font-black">
            GW {match.gameweek}
          </span>
          <span className="flex items-center gap-1 font-semibold text-ink-secondary text-xs">
            <Calendar size={13} className="text-ink-secondary" />
            {formatKickoff(match.kickoff_time)}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "inline-flex items-center rounded-full border px-2.5 py-0.5 text-[10px] font-black uppercase tracking-wide",
              confidenceTone,
            )}
          >
            {match.confidence_level} Confidence
          </span>
        </div>
      </div>

      {/* Main Clash Header: Equal Visual Balance */}
      <div className="py-4">
        <div className="grid grid-cols-7 items-center gap-2">
          {/* Home Team */}
          <div className="col-span-3 flex flex-col items-center text-center sm:items-start sm:text-left">
            <div className="flex items-center gap-2.5 mb-1.5">
              <TeamBadge
                team={match.home_team}
                logoUrl={match.home_team_logo_url}
                size="md"
              />
              <span className="hidden font-display text-sm sm:text-base font-black text-ink-primary sm:inline line-clamp-1">
                {match.home_team}
              </span>
            </div>
            <span className="font-display text-xs font-black text-ink-primary sm:hidden truncate max-w-[90px]">
              {match.home_team}
            </span>
            <div className="inline-flex items-center gap-1 rounded-md bg-ivory-subtle px-2 py-0.5 text-[10px] font-bold text-ink-secondary border border-border">
              <span>xG</span>
              <span className="numeral font-black text-ink-primary">
                {Math.round(match.predicted_home_goals)}
              </span>
            </div>
          </div>

          {/* Predicted Scoreline */}
          <div className="col-span-1 flex flex-col items-center justify-center text-center">
            <div className="font-display text-lg sm:text-2xl font-black tracking-tight text-stadium-deep bg-ivory-subtle px-2.5 py-1 rounded-xl border border-border shadow-inner">
              {match.predicted_scoreline}
            </div>
            <span className="mt-1 font-mono text-[9px] font-bold uppercase text-ink-secondary">
              Projected
            </span>
          </div>

          {/* Away Team */}
          <div className="col-span-3 flex flex-col items-center text-center sm:items-end sm:text-right">
            <div className="flex items-center gap-2.5 mb-1.5 flex-row-reverse sm:flex-row">
              <span className="hidden font-display text-sm sm:text-base font-black text-ink-primary sm:inline line-clamp-1">
                {match.away_team}
              </span>
              <TeamBadge
                team={match.away_team}
                logoUrl={match.away_team_logo_url}
                size="md"
              />
            </div>
            <span className="font-display text-xs font-black text-ink-primary sm:hidden truncate max-w-[90px]">
              {match.away_team}
            </span>
            <div className="inline-flex items-center gap-1 rounded-md bg-ivory-subtle px-2 py-0.5 text-[10px] font-bold text-ink-secondary border border-border">
              <span>xG</span>
              <span className="numeral font-black text-ink-primary">
                {Math.round(match.predicted_away_goals)}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Dominant 3-Outcome Probabilities */}
      <div className="pt-1">
        <OutcomeProbabilityBar
          homeTeam={match.home_team}
          awayTeam={match.away_team}
          homeProb={match.home_win_probability}
          drawProb={match.draw_probability}
          awayProb={match.away_win_probability}
          predictedResult={match.predicted_result}
        />
      </div>

      {/* Secondary Fantasy Impact Strip */}
      <div className="mt-4 pt-3 border-t border-border/70 flex items-center justify-between">
        <div className="flex items-center gap-2 flex-wrap">
          {match.best_captain_candidate && (
            <div className="inline-flex items-center gap-1.5 rounded-md bg-gold-light px-2.5 py-1 text-[10px] font-bold text-gold-dark border border-gold-border">
              <Crown size={12} className="text-gold-metallic" />
              <span className="truncate max-w-[120px]">
                {match.best_captain_candidate.name}
              </span>
              {match.best_captain_candidate.expected_points && (
                <span className="numeral font-black text-gold-dark">
                  {Math.round(match.best_captain_candidate.expected_points)} xPts
                </span>
              )}
            </div>
          )}

          {typeof match.over_2_5_probability === "number" && (
            <span className="rounded-md bg-ivory-subtle px-2 py-0.5 text-[10px] font-bold text-ink-secondary border border-border">
              Over 2.5: {Math.round(match.over_2_5_probability * 100)}%
            </span>
          )}
        </div>

        <span className="inline-flex items-center gap-1 text-xs font-black text-stadium-deep group-hover:text-gold-metallic group-hover:translate-x-0.5 transition-all">
          <span>Matchday Intel</span>
          <ChevronRight size={14} />
        </span>
      </div>
    </article>
  );
}
