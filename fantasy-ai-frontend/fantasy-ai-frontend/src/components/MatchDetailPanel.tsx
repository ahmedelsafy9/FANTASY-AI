import React from "react";
import {
  Crown,
  Crosshair,
  Shield,
  Sparkles,
  Activity,
  Award,
} from "lucide-react";
import type { MatchPrediction, MatchPlayerImpact } from "@/types/api";
import { TeamBadge, PlayerAvatar } from "@/components/identity";
import { AdvancedToggle } from "@/components/AdvancedToggle";
import { OutcomeProbabilityBar } from "@/components/OutcomeProbabilityBar";
import { cn } from "@/lib/utils";

interface MatchDetailPanelProps {
  match: MatchPrediction | null;
}

function formatKickoff(dateStr?: string | null): string {
  if (!dateStr) return "Fixture Date TBD";
  try {
    const d = new Date(dateStr);
    if (Number.isNaN(d.getTime())) return dateStr;
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
    <div className="flex items-center gap-3 rounded-xl border border-border bg-ivory-surface p-3 transition-colors hover:border-gold-metallic/60 shadow-xs">
      <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="md" />
      <div className="min-w-0 flex-1">
        {badgeTitle && BadgeIcon && (
          <div className="mb-1 flex items-center gap-1">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-black uppercase tracking-wider",
                badgeColor ?? "bg-gold-light text-gold-dark border border-gold-border",
              )}
            >
              <BadgeIcon size={10} />
              {badgeTitle}
            </span>
          </div>
        )}
        <div className="font-display text-sm font-black text-ink-primary truncate">
          {player.name}
        </div>
        <div className="flex items-center gap-2 text-[11px] font-bold text-ink-secondary">
          <span className="rounded bg-ivory-subtle px-1.5 py-0.2 border border-border">
            {player.position ?? "N/A"}
          </span>
          <span>{player.team}</span>
        </div>
      </div>
      <div className="text-right shrink-0">
        <div className="numeral text-sm font-black text-stadium-deep">
          {player.expected_points != null ? `${Math.round(player.expected_points)} xPts` : "—"}
        </div>
      </div>
    </div>
  );
}

export function MatchDetailPanel({ match }: MatchDetailPanelProps) {
  if (!match) return null;

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
    <div className="space-y-6 pb-8 text-ink-primary">
      {/* Header Matchup */}
      <div className="border-b border-border pb-5">
        <div className="flex items-center justify-between text-xs text-ink-secondary mb-3">
          <span className="rounded-md bg-stadium-deep text-ivory-surface px-2.5 py-1 font-mono font-bold">
            Gameweek {match.gameweek}
          </span>
          <span className="font-semibold">{formatKickoff(match.kickoff_time)}</span>
        </div>

        {/* Teams Clash */}
        <div className="flex items-center justify-between gap-3 pt-2">
          <div className="flex flex-col items-center gap-1.5 flex-1 text-center">
            <TeamBadge
              team={match.home_team}
              logoUrl={match.home_team_logo_url}
              size="lg"
            />
            <span className="font-display text-sm font-black text-ink-primary line-clamp-1">
              {match.home_team}
            </span>
            <span className="rounded-full bg-ivory-subtle px-2 py-0.5 text-[10px] font-black text-ink-secondary border border-border">
              Home
            </span>
          </div>

          <div className="flex flex-col items-center justify-center shrink-0 px-2">
            <span className="font-mono text-2xl sm:text-3xl font-black tracking-tight text-stadium-deep bg-ivory-subtle px-3 py-1 rounded-xl border border-border shadow-inner">
              {match.predicted_scoreline}
            </span>
            <span className="text-[10px] font-black uppercase text-ink-secondary tracking-wider mt-1">
              Projected
            </span>
          </div>

          <div className="flex flex-col items-center gap-1.5 flex-1 text-center">
            <TeamBadge
              team={match.away_team}
              logoUrl={match.away_team_logo_url}
              size="lg"
            />
            <span className="font-display text-sm font-black text-ink-primary line-clamp-1">
              {match.away_team}
            </span>
            <span className="rounded-full bg-ivory-subtle px-2 py-0.5 text-[10px] font-black text-ink-secondary border border-border">
              Away
            </span>
          </div>
        </div>

        {/* Confidence Banner */}
        <div className="mt-4 flex items-center justify-between rounded-xl bg-ivory-subtle p-3 border border-border">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-gold-metallic" />
            <span className="text-xs font-bold text-ink-primary">
              Model Prediction Confidence:{" "}
              <strong className="text-stadium-deep">{match.confidence_level}</strong>
            </span>
          </div>
        </div>
      </div>

      {/* Win/Draw/Loss Outcome Probabilities */}
      <div className="space-y-3">
        <h4 className="text-xs font-black uppercase tracking-wider text-ink-primary flex items-center gap-1.5">
          <Activity size={14} className="text-gold-metallic" />
          Three-Outcome Probability Distribution
        </h4>

        <OutcomeProbabilityBar
          homeTeam={match.home_team}
          awayTeam={match.away_team}
          homeProb={match.home_win_probability}
          drawProb={match.draw_probability}
          awayProb={match.away_win_probability}
          predictedResult={match.predicted_result}
        />
      </div>

      {/* Expected Goals & Goal Markets */}
      <div className="space-y-3">
        <h4 className="text-xs font-black uppercase tracking-wider text-ink-primary flex items-center gap-1.5">
          <Crosshair size={14} className="text-stadium-forest" />
          Expected Goals & Probability Markets
        </h4>

        {/* xG Comparison */}
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl border border-border bg-ivory-surface p-3 shadow-xs">
            <div className="text-[11px] font-bold text-ink-secondary truncate">
              {match.home_team} xG
            </div>
            <div className="numeral text-lg font-black text-stadium-deep mt-0.5">
              {Math.round(match.predicted_home_goals)}
            </div>
            <div className="text-[10px] font-semibold text-ink-secondary mt-0.5">
              Projected goals generated
            </div>
          </div>

          <div className="rounded-xl border border-border bg-ivory-surface p-3 shadow-xs">
            <div className="text-[11px] font-bold text-ink-secondary truncate">
              {match.away_team} xG
            </div>
            <div className="numeral text-lg font-black text-stadium-deep mt-0.5">
              {Math.round(match.predicted_away_goals)}
            </div>
            <div className="text-[10px] font-semibold text-ink-secondary mt-0.5">
              Projected goals generated
            </div>
          </div>
        </div>

        {/* Goal Markets Strip */}
        <div className="grid grid-cols-2 gap-2 text-xs">
          {o25Pct != null && (
            <div className="flex items-center justify-between rounded-lg border border-border bg-ivory-subtle p-2.5">
              <span className="font-bold text-ink-secondary">Over 2.5 Goals</span>
              <span className="numeral font-black text-ink-primary">
                {o25Pct}%
              </span>
            </div>
          )}
          {u25Pct != null && (
            <div className="flex items-center justify-between rounded-lg border border-border bg-ivory-subtle p-2.5">
              <span className="font-bold text-ink-secondary">Under 2.5 Goals</span>
              <span className="numeral font-black text-ink-primary">
                {u25Pct}%
              </span>
            </div>
          )}
          {bttsPct != null && (
            <div className="flex items-center justify-between rounded-lg border border-border bg-ivory-subtle p-2.5">
              <span className="font-bold text-ink-secondary">Both Teams Score</span>
              <span className="numeral font-black text-ink-primary">
                {bttsPct}%
              </span>
            </div>
          )}
          {hCsPct != null && (
            <div className="flex items-center justify-between rounded-lg border border-border bg-ivory-subtle p-2.5">
              <span className="font-bold text-ink-secondary truncate">
                {match.home_team} Clean Sheet
              </span>
              <span className="numeral font-black text-ink-primary">
                {hCsPct}%
              </span>
            </div>
          )}
          {aCsPct != null && (
            <div className="flex items-center justify-between rounded-lg border border-border bg-ivory-subtle p-2.5">
              <span className="font-bold text-ink-secondary truncate">
                {match.away_team} Clean Sheet
              </span>
              <span className="numeral font-black text-ink-primary">
                {aCsPct}%
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Model Statistical Drivers */}
      {drivers && (
        <AdvancedToggle label="Match statistical drivers">
          <div className="space-y-2 pt-1">
            <div className="grid grid-cols-2 gap-2 text-xs">
              {drivers.home_attack_strength != null && (
                <div className="rounded-lg border border-border bg-ivory-surface p-2.5">
                  <span className="text-[10px] font-bold text-ink-secondary block truncate">
                    {match.home_team} Attack
                  </span>
                  <span className="numeral font-black text-ink-primary">
                    {Number(drivers.home_attack_strength).toFixed(2)}
                  </span>
                </div>
              )}
              {drivers.away_attack_strength != null && (
                <div className="rounded-lg border border-border bg-ivory-surface p-2.5">
                  <span className="text-[10px] font-bold text-ink-secondary block truncate">
                    {match.away_team} Attack
                  </span>
                  <span className="numeral font-black text-ink-primary">
                    {Number(drivers.away_attack_strength).toFixed(2)}
                  </span>
                </div>
              )}
              {drivers.home_defence_strength != null && (
                <div className="rounded-lg border border-border bg-ivory-surface p-2.5">
                  <span className="text-[10px] font-bold text-ink-secondary block truncate">
                    {match.home_team} Defence
                  </span>
                  <span className="numeral font-black text-ink-primary">
                    {Number(drivers.home_defence_strength).toFixed(2)}
                  </span>
                </div>
              )}
              {drivers.away_defence_strength != null && (
                <div className="rounded-lg border border-border bg-ivory-surface p-2.5">
                  <span className="text-[10px] font-bold text-ink-secondary block truncate">
                    {match.away_team} Defence
                  </span>
                  <span className="numeral font-black text-ink-primary">
                    {Number(drivers.away_defence_strength).toFixed(2)}
                  </span>
                </div>
              )}
            </div>
          </div>
        </AdvancedToggle>
      )}

      {/* Fantasy Impact Section */}
      <div className="space-y-4 pt-2 border-t border-border">
        <div>
          <h4 className="text-xs font-black uppercase tracking-wider text-ink-primary flex items-center gap-1.5">
            <Award size={14} className="text-gold-metallic" />
            Tactical Fantasy Recommendations
          </h4>
          <p className="text-[11px] font-semibold text-ink-secondary mt-0.5">
            Key assets to target for this fixture based on expected points and game state.
          </p>
        </div>

        {/* Priority Recommended Roles */}
        <div className="space-y-2">
          {match.best_captain_candidate && (
            <PlayerImpactCard
              player={match.best_captain_candidate}
              badgeTitle="Best Armband Candidate"
              badgeIcon={Crown}
              badgeColor="bg-gold-light text-gold-dark border border-gold-border"
            />
          )}

          {match.best_attacking_option && (
            <PlayerImpactCard
              player={match.best_attacking_option}
              badgeTitle="Top Attacking Target"
              badgeIcon={Crosshair}
              badgeColor="bg-ivory-subtle text-stadium-deep border border-border"
            />
          )}

          {match.best_defensive_option && (
            <PlayerImpactCard
              player={match.best_defensive_option}
              badgeTitle="Top Clean Sheet Potential"
              badgeIcon={Shield}
              badgeColor="bg-ivory-subtle text-stadium-forest border border-border"
            />
          )}
        </div>

        {/* Top Players by Team */}
        {((match.top_home_players && match.top_home_players.length > 0) ||
          (match.top_away_players && match.top_away_players.length > 0)) && (
          <div className="space-y-4 pt-2">
            {match.top_home_players && match.top_home_players.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] font-black uppercase tracking-wider text-ink-secondary">
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
                <div className="text-[11px] font-black uppercase tracking-wider text-ink-secondary">
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
