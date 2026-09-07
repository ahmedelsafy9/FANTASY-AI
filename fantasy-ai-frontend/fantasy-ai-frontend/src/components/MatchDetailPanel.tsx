import {
  Crown,
  Crosshair,
  Shield,
  Sparkles,
  Activity,
  Award,
  Zap,
} from "lucide-react";
import type { MatchPrediction, MatchPlayerImpact } from "@/types/api";
import { TeamBadge, PlayerAvatar } from "@/components/identity";
import { cn } from "@/lib/utils";

interface MatchDetailPanelProps {
  match: MatchPrediction | null;
}

function formatKickoff(dateStr?: string | null): string {
  if (!dateStr) return "TBD";
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString("en-GB", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

function PlayerImpactCard({
  player,
  badgeTitle,
  badgeIcon: BadgeIcon,
  badgeColor,
}: {
  player: MatchPlayerImpact;
  badgeTitle?: string;
  badgeIcon?: React.ElementType;
  badgeColor?: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-[#E2E8F0] bg-[#F8FAFC] p-3 transition-colors hover:border-[#10B981] hover:bg-white">
      <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="md" />
      <div className="min-w-0 flex-1">
        {badgeTitle && BadgeIcon && (
          <div className="mb-1 flex items-center gap-1">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-black uppercase tracking-wider",
                badgeColor ?? "bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]"
              )}
            >
              <BadgeIcon size={10} />
              {badgeTitle}
            </span>
          </div>
        )}
        <div className="font-display text-sm font-black text-[#0F172A] truncate">
          {player.name}
        </div>
        <div className="flex items-center gap-2 text-[11px] font-bold text-[#64748B]">
          <span className="rounded bg-white px-1.5 py-0.2 border border-[#E2E8F0]">
            {player.position ?? "N/A"}
          </span>
          <span>{player.team}</span>
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className="font-mono text-sm font-black text-[#10B981]">
          {player.expected_points != null ? `${player.expected_points.toFixed(1)} xPts` : "—"}
        </div>
        {player.fpl_rank_score != null && (
          <div className="text-[10px] font-mono font-bold text-[#64748B]">
            Rank: {player.fpl_rank_score.toFixed(1)}
          </div>
        )}
      </div>
    </div>
  );
}

export function MatchDetailPanel({ match }: MatchDetailPanelProps) {
  if (!match) return null;

  const hwPct = Math.round(match.home_win_probability * 100);
  const drPct = Math.round(match.draw_probability * 100);
  const awPct = Math.round(match.away_win_probability * 100);

  const o25Pct =
    typeof match.over_2_5_probability === "number"
      ? Math.round(match.over_2_5_probability * 100)
      : null;
  const u25Pct =
    typeof match.under_2_5_probability === "number"
      ? Math.round(match.under_2_5_probability * 100)
      : o25Pct != null
      ? 100 - o25Pct
      : null;

  const bttsPct =
    typeof match.btts_probability === "number"
      ? Math.round(match.btts_probability * 100)
      : null;

  const hCsPct =
    typeof match.home_clean_sheet_probability === "number"
      ? Math.round(match.home_clean_sheet_probability * 100)
      : null;
  const aCsPct =
    typeof match.away_clean_sheet_probability === "number"
      ? Math.round(match.away_clean_sheet_probability * 100)
      : null;

  const drivers = match.prediction_drivers;

  return (
    <div className="space-y-6 pb-8">
      {/* Header Matchup */}
      <div className="border-b border-[#E2E8F0] pb-5">
        <div className="flex items-center justify-between text-xs text-[#64748B] mb-3">
          <span className="rounded-md bg-[#F1F5F9] px-2.5 py-1 font-mono font-bold text-[#334155]">
            Gameweek {match.gameweek}
          </span>
          <span className="font-semibold">{formatKickoff(match.kickoff_time)}</span>
        </div>

        {/* Big Teams Clash */}
        <div className="flex items-center justify-between gap-3 pt-2">
          <div className="flex flex-col items-center gap-1.5 flex-1 text-center">
            <TeamBadge
              team={match.home_team}
              logoUrl={match.home_team_logo_url}
              size="lg"
            />
            <span className="font-display text-sm font-black text-[#0F172A] line-clamp-1">
              {match.home_team}
            </span>
            <span className="rounded-full bg-[#ECFDF5] px-2 py-0.5 text-[10px] font-black text-[#059669] border border-[#A7F3D0]">
              Home
            </span>
          </div>

          <div className="flex flex-col items-center justify-center shrink-0 px-2">
            <span className="font-mono text-2xl font-black tracking-tight text-[#0F172A]">
              {match.predicted_scoreline}
            </span>
            <span className="text-[10px] font-black uppercase text-[#64748B] tracking-wider mt-0.5">
              Predicted
            </span>
          </div>

          <div className="flex flex-col items-center gap-1.5 flex-1 text-center">
            <TeamBadge
              team={match.away_team}
              logoUrl={match.away_team_logo_url}
              size="lg"
            />
            <span className="font-display text-sm font-black text-[#0F172A] line-clamp-1">
              {match.away_team}
            </span>
            <span className="rounded-full bg-[#F1F5F9] px-2 py-0.5 text-[10px] font-black text-[#475569] border border-[#CBD5E1]">
              Away
            </span>
          </div>
        </div>

        {/* Confidence Banner */}
        <div className="mt-4 flex items-center justify-between rounded-xl bg-[#F8FAFC] p-2.5 border border-[#E2E8F0]">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-[#10B981]" />
            <span className="text-xs font-bold text-[#334155]">
              Model Confidence:{" "}
              <strong className="text-[#0F172A]">{match.confidence_level}</strong>
            </span>
          </div>
          <span className="font-mono text-xs font-black text-[#10B981]">
            {Math.round(match.confidence * 100)}%
          </span>
        </div>
      </div>

      {/* Win/Draw/Loss Outcome Probabilities */}
      <div className="space-y-3">
        <h4 className="text-xs font-black uppercase tracking-wider text-[#0F172A] flex items-center gap-1.5">
          <Activity size={14} className="text-[#10B981]" />
          Match Outcome Probabilities (Poisson)
        </h4>

        <div className="grid grid-cols-3 gap-2 text-center">
          <div
            className={cn(
              "rounded-xl border p-3 transition-colors",
              match.predicted_result === "HOME_WIN"
                ? "border-[#10B981] bg-[#ECFDF5]/50"
                : "border-[#E2E8F0] bg-white"
            )}
          >
            <div className="text-[11px] font-bold text-[#64748B] truncate">
              {match.home_team} Win
            </div>
            <div className="font-mono text-xl font-black text-[#059669] mt-1">
              {hwPct}%
            </div>
            {match.predicted_result === "HOME_WIN" && (
              <span className="inline-block mt-1 rounded bg-[#10B981] text-white px-1.5 py-0.2 text-[9px] font-black uppercase">
                Favored
              </span>
            )}
          </div>

          <div
            className={cn(
              "rounded-xl border p-3 transition-colors",
              match.predicted_result === "DRAW"
                ? "border-[#F59E0B] bg-[#FFFBEB]/50"
                : "border-[#E2E8F0] bg-white"
            )}
          >
            <div className="text-[11px] font-bold text-[#64748B]">Draw</div>
            <div className="font-mono text-xl font-black text-[#D97706] mt-1">
              {drPct}%
            </div>
            {match.predicted_result === "DRAW" && (
              <span className="inline-block mt-1 rounded bg-[#F59E0B] text-white px-1.5 py-0.2 text-[9px] font-black uppercase">
                Favored
              </span>
            )}
          </div>

          <div
            className={cn(
              "rounded-xl border p-3 transition-colors",
              match.predicted_result === "AWAY_WIN"
                ? "border-[#6366F1] bg-[#EEF2FF]/50"
                : "border-[#E2E8F0] bg-white"
            )}
          >
            <div className="text-[11px] font-bold text-[#64748B] truncate">
              {match.away_team} Win
            </div>
            <div className="font-mono text-xl font-black text-[#4F46E5] mt-1">
              {awPct}%
            </div>
            {match.predicted_result === "AWAY_WIN" && (
              <span className="inline-block mt-1 rounded bg-[#6366F1] text-white px-1.5 py-0.2 text-[9px] font-black uppercase">
                Favored
              </span>
            )}
          </div>
        </div>

        {/* Segmented bar */}
        <div className="flex h-3 w-full overflow-hidden rounded-full bg-[#F1F5F9] p-0.5 border border-[#E2E8F0]">
          <div
            style={{ width: `${hwPct}%` }}
            className="h-full rounded-l-full bg-[#10B981]"
          />
          <div style={{ width: `${drPct}%` }} className="h-full bg-[#F59E0B]" />
          <div
            style={{ width: `${awPct}%` }}
            className="h-full rounded-r-full bg-[#6366F1]"
          />
        </div>
      </div>

      {/* Expected Goals & Goal Markets */}
      <div className="space-y-3">
        <h4 className="text-xs font-black uppercase tracking-wider text-[#0F172A] flex items-center gap-1.5">
          <Crosshair size={14} className="text-[#10B981]" />
          Expected Goals & Markets
        </h4>

        {/* xG Comparison */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-[#E2E8F0] bg-white p-3">
            <div className="text-[11px] font-bold text-[#64748B] truncate">
              {match.home_team} xG
            </div>
            <div className="font-mono text-lg font-black text-[#0F172A] mt-0.5">
              {match.predicted_home_goals.toFixed(2)}
            </div>
            <div className="text-[10px] font-semibold text-[#64748B] mt-1">
              Expected goals generated
            </div>
          </div>

          <div className="rounded-xl border border-[#E2E8F0] bg-white p-3">
            <div className="text-[11px] font-bold text-[#64748B] truncate">
              {match.away_team} xG
            </div>
            <div className="font-mono text-lg font-black text-[#0F172A] mt-0.5">
              {match.predicted_away_goals.toFixed(2)}
            </div>
            <div className="text-[10px] font-semibold text-[#64748B] mt-1">
              Expected goals generated
            </div>
          </div>
        </div>

        {/* Goal Markets Strip */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          {o25Pct != null && (
            <div className="flex items-center justify-between rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <span className="font-bold text-[#475569]">Over 2.5 Goals</span>
              <span className="font-mono font-black text-[#0F172A]">
                {o25Pct}%
              </span>
            </div>
          )}
          {u25Pct != null && (
            <div className="flex items-center justify-between rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <span className="font-bold text-[#475569]">Under 2.5 Goals</span>
              <span className="font-mono font-black text-[#0F172A]">
                {u25Pct}%
              </span>
            </div>
          )}
          {bttsPct != null && (
            <div className="flex items-center justify-between rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <span className="font-bold text-[#475569]">Both Score (BTTS)</span>
              <span className="font-mono font-black text-[#0F172A]">
                {bttsPct}%
              </span>
            </div>
          )}
          {hCsPct != null && (
            <div className="flex items-center justify-between rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <span className="font-bold text-[#475569] truncate">
                {match.home_team} Clean Sheet
              </span>
              <span className="font-mono font-black text-[#0F172A]">
                {hCsPct}%
              </span>
            </div>
          )}
          {aCsPct != null && (
            <div className="flex items-center justify-between rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-2.5">
              <span className="font-bold text-[#475569] truncate">
                {match.away_team} Clean Sheet
              </span>
              <span className="font-mono font-black text-[#0F172A]">
                {aCsPct}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Model Statistical Drivers */}
      {drivers && (
        <div className="space-y-3">
          <h4 className="text-xs font-black uppercase tracking-wider text-[#0F172A] flex items-center gap-1.5">
            <Zap size={14} className="text-[#10B981]" />
            Match Model Features
          </h4>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {drivers.home_attack_strength != null && (
              <div className="rounded-lg border border-[#E2E8F0] bg-white p-2.5">
                <span className="text-[10px] font-bold text-[#64748B] block truncate">
                  {match.home_team} Attack
                </span>
                <span className="font-mono font-black text-[#0F172A]">
                  {Number(drivers.home_attack_strength).toFixed(2)}
                </span>
              </div>
            )}
            {drivers.away_attack_strength != null && (
              <div className="rounded-lg border border-[#E2E8F0] bg-white p-2.5">
                <span className="text-[10px] font-bold text-[#64748B] block truncate">
                  {match.away_team} Attack
                </span>
                <span className="font-mono font-black text-[#0F172A]">
                  {Number(drivers.away_attack_strength).toFixed(2)}
                </span>
              </div>
            )}
            {drivers.home_defence_strength != null && (
              <div className="rounded-lg border border-[#E2E8F0] bg-white p-2.5">
                <span className="text-[10px] font-bold text-[#64748B] block truncate">
                  {match.home_team} Defence
                </span>
                <span className="font-mono font-black text-[#0F172A]">
                  {Number(drivers.home_defence_strength).toFixed(2)}
                </span>
              </div>
            )}
            {drivers.away_defence_strength != null && (
              <div className="rounded-lg border border-[#E2E8F0] bg-white p-2.5">
                <span className="text-[10px] font-bold text-[#64748B] block truncate">
                  {match.away_team} Defence
                </span>
                <span className="font-mono font-black text-[#0F172A]">
                  {Number(drivers.away_defence_strength).toFixed(2)}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Fantasy Impact Section */}
      <div className="space-y-4 pt-2 border-t border-[#E2E8F0]">
        <div>
          <h4 className="text-xs font-black uppercase tracking-wider text-[#0F172A] flex items-center gap-1.5">
            <Award size={14} className="text-[#F59E0B]" />
            Fantasy Impact Highlights
          </h4>
          <p className="text-[11px] font-semibold text-[#64748B] mt-0.5">
            Derived directly from authoritative Feedback 5 player prediction pipeline.
          </p>
        </div>

        {/* Priority Recommended Roles */}
        <div className="space-y-2">
          {match.best_captain_candidate && (
            <PlayerImpactCard
              player={match.best_captain_candidate}
              badgeTitle="Best Captain Pick"
              badgeIcon={Crown}
              badgeColor="bg-[#FEF3C7] text-[#92400E] border border-[#FDE68A]"
            />
          )}

          {match.best_attacking_option && (
            <PlayerImpactCard
              player={match.best_attacking_option}
              badgeTitle="Top Attacking Asset"
              badgeIcon={Crosshair}
              badgeColor="bg-[#ECFDF5] text-[#059669] border border-[#A7F3D0]"
            />
          )}

          {match.best_defensive_option && (
            <PlayerImpactCard
              player={match.best_defensive_option}
              badgeTitle="Top Defensive Asset"
              badgeIcon={Shield}
              badgeColor="bg-[#EEF2FF] text-[#4F46E5] border border-indigo-200"
            />
          )}
        </div>

        {/* Top Players by Team */}
        {((match.top_home_players && match.top_home_players.length > 0) ||
          (match.top_away_players && match.top_away_players.length > 0)) && (
          <div className="space-y-4 pt-2">
            {match.top_home_players && match.top_home_players.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] font-black uppercase tracking-wider text-[#475569]">
                  Top {match.home_team} Projected Assets
                </div>
                <div className="space-y-1.5">
                  {match.top_home_players.map((p) => (
                    <PlayerImpactCard key={p.element ?? p.name} player={p} />
                  ))}
                </div>
              </div>
            )}

            {match.top_away_players && match.top_away_players.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] font-black uppercase tracking-wider text-[#475569]">
                  Top {match.away_team} Projected Assets
                </div>
                <div className="space-y-1.5">
                  {match.top_away_players.map((p) => (
                    <PlayerImpactCard key={p.element ?? p.name} player={p} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
