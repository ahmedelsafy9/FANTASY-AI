import { Link } from "react-router-dom";
import {
  Sparkles,
  Trophy,
  Shield,
  ArrowRight,
  Zap,
  Crown,
  Calendar,
  Users,
  TrendingUp,
} from "lucide-react";
import { useTopPlayers, useCaptain, useMatchPredictions } from "@/hooks/useApi";
import { PlayerCard } from "@/components/PlayerCard";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { ExpectedPoints } from "@/components/ExpectedPoints";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { OutcomeProbabilityBar } from "@/components/OutcomeProbabilityBar";
import { deriveConfidenceLevel } from "@/lib/insights";
import { PlayerCardSkeleton, ErrorState } from "@/components/states";
import { Button, Card } from "@/components/ui/primitives";
import { formatPrice } from "@/lib/format";
import { AssistantIcon } from "@/components/brand/AssistantIcon";

export default function Home() {
  const { data: topData, loading: topLoading, error: topError, refetch: refetchTop } = useTopPlayers(6);
  const { data: capData, loading: capLoading } = useCaptain();
  const { data: matchData } = useMatchPredictions();

  const topPlayers = topData?.predictions ?? [];
  const targetGw = topData?.predicted_gameweek ?? topPlayers[0]?.predicted_for_gw ?? 1;

  const captain = capData?.recommendation;
  const featuredPick = topPlayers.find((p) => p.name !== captain?.name) ?? topPlayers[0];
  const featuredMatch = matchData?.predictions?.[0];

  return (
    <div className="mx-auto max-w-7xl px-4 py-8 pb-safe-bottom sm:px-6 lg:px-8 space-y-10">
      {/* Hero Section — Stadium Luxe Night Football Arena */}
      <section className="relative overflow-hidden rounded-3xl border border-gold-border/40 bg-gradient-to-br from-stadium-deep via-stadium-surface to-stadium-dark p-7 sm:p-12 text-ivory-surface shadow-card">
        {/* Stadium Floodlight Radial Accents */}
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-gold-metallic/15 blur-3xl pointer-events-none" />
        <div className="absolute -left-24 -bottom-24 h-80 w-80 rounded-full bg-stadium-forest/40 blur-3xl pointer-events-none" />
        {/* Subtle Pitch Geometry Watermark */}
        <div className="absolute right-8 bottom-0 w-80 h-40 opacity-10 pointer-events-none border-2 border-gold-bright rounded-t-full" />

        <div className="relative z-10 max-w-3xl">
          {/* Tactical Gameweek Badge */}
          <div className="inline-flex items-center gap-2 rounded-full border border-gold-border/70 bg-gold-light/10 backdrop-blur-md px-4 py-1.5 text-xs font-black text-gold-bright shadow-xs mb-5 select-none">
            <Sparkles size={14} className="text-gold-bright" />
            <span>Gameweek {targetGw} Tactical Intelligence</span>
          </div>

          {/* Headline */}
          <h1 className="font-display text-3xl font-black text-ivory-surface sm:text-5xl lg:text-6xl leading-[1.1] tracking-tight">
            Decisive FPL Advantage, <span className="text-gradient-gold">Engineered to Win.</span>
          </h1>

          <p className="mt-4 text-base font-medium text-ink-light-secondary sm:text-lg leading-relaxed max-w-2xl">
            Whole-number predicted points, unmistakable match probabilities, and an AI co-pilot designed to give you clarity and confidence every deadline.
          </p>

          {/* Action Callouts */}
          <div className="mt-8 flex flex-wrap items-center gap-3.5">
            <Link to="/players">
              <Button size="lg" className="gap-2 text-sm font-black bg-gold-metallic text-stadium-dark border border-gold-border shadow-glow-gold hover:bg-gold-bright">
                <Users size={18} />
                <span>Player Predictions</span>
              </Button>
            </Link>

            <Link to="/match-predictions">
              <Button size="lg" className="gap-2 text-sm font-black bg-stadium-surface/80 hover:bg-stadium-forest text-ivory-surface border border-gold-border/40 backdrop-blur-sm">
                <Trophy size={18} className="text-gold-bright" />
                <span>Match Probabilities</span>
              </Button>
            </Link>

            <Link to="/assistant">
              <Button size="lg" className="gap-2 text-sm font-black bg-ivory-surface/10 hover:bg-ivory-surface/20 text-gold-bright border border-gold-border/30 backdrop-blur-sm">
                <AssistantIcon size="sm" />
                <span>Ask Wizard AI</span>
              </Button>
            </Link>
          </div>
        </div>
      </section>

      {/* Gameweek Decision Spotlight: Captain, Top Pick, Featured Match */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-xl sm:text-2xl font-black text-ink-primary flex items-center gap-2">
            <Zap size={22} className="text-gold-metallic" />
            <span>Crucial Decisions for Gameweek {targetGw}</span>
          </h2>
          <span className="text-xs font-bold text-ink-secondary hidden sm:inline">
            Synchronized with official deadline models
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Spotlight 1: Recommended Captain */}
          <Card className="flex flex-col justify-between border-gold-border/80 bg-ivory-surface p-5 shadow-card hover:border-gold-metallic transition-all">
            <div>
              <div className="flex items-center justify-between mb-3.5">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-gold-light border border-gold-border px-3 py-1 text-[10px] font-black uppercase text-gold-dark">
                  <Crown size={13} className="text-gold-metallic" />
                  Armband Recommendation
                </span>
                <span className="font-mono text-xs font-black text-gold-dark bg-gold-light px-2 py-0.5 rounded border border-gold-border">
                  2× Points
                </span>
              </div>

              {captain ? (
                <div className="flex items-center gap-3.5">
                  <PlayerAvatar
                    name={captain.name}
                    photoUrl={captain.photo_url}
                    size="lg"
                    className="ring-2 ring-gold-metallic/60 shadow-xs"
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display font-black text-base text-ink-primary truncate">
                      {captain.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-1 text-xs text-ink-secondary font-semibold">
                      <TeamBadge team={captain.team} logoUrl={captain.team_logo_url} size="sm" showName />
                      <ConfidenceBadge level={deriveConfidenceLevel(captain)} showTooltip={false} />
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <ExpectedPoints
                      points={captain.predicted_expected_points ?? captain.predicted_total_points}
                      size="sm"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-sm font-semibold text-ink-secondary py-3">
                  {capLoading ? "Calculating optimal captain pick..." : "Captain recommendation ready"}
                </div>
              )}

              {capData?.reasoning && (
                <p className="mt-3.5 text-xs font-semibold text-ink-secondary line-clamp-2 leading-relaxed">
                  {capData.reasoning}
                </p>
              )}
            </div>

            <Link
              to="/captain"
              className="mt-5 pt-3 border-t border-border flex items-center justify-between text-xs font-black text-gold-dark hover:text-ink-primary transition-colors"
            >
              <span>Full Captaincy Assessment</span>
              <ArrowRight size={14} />
            </Link>
          </Card>

          {/* Spotlight 2: Top Projected Performer */}
          <Card className="flex flex-col justify-between border-border bg-ivory-surface p-5 shadow-card hover:border-gold-border transition-all">
            <div>
              <div className="flex items-center justify-between mb-3.5">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-stadium-surface/10 border border-border px-3 py-1 text-[10px] font-black uppercase text-stadium-deep">
                  <TrendingUp size={13} className="text-stadium-deep" />
                  Top Projected Asset
                </span>
                <span className="text-[10px] font-bold text-ink-secondary">
                  GW {targetGw}
                </span>
              </div>

              {featuredPick ? (
                <div className="flex items-center gap-3.5">
                  <PlayerAvatar
                    name={featuredPick.name}
                    photoUrl={featuredPick.photo_url}
                    size="lg"
                    className="ring-2 ring-stadium-forest/30 shadow-xs"
                  />
                  <div className="min-w-0 flex-1">
                    <h3 className="font-display font-black text-base text-ink-primary truncate">
                      {featuredPick.name}
                    </h3>
                    <div className="flex items-center gap-2 mt-1 text-xs text-ink-secondary font-semibold">
                      <span>{featuredPick.team}</span>
                      <span>•</span>
                      <span className="text-ink-primary font-bold">
                        £{formatPrice(featuredPick.value ?? (typeof featuredPick.now_cost === "number" ? featuredPick.now_cost : 50))}
                      </span>
                    </div>
                  </div>
                  <div className="text-right shrink-0">
                    <ExpectedPoints
                      points={featuredPick.predicted_expected_points ?? featuredPick.predicted_total_points}
                      size="sm"
                    />
                  </div>
                </div>
              ) : (
                <div className="text-sm font-semibold text-ink-secondary py-3">
                  Projecting top performers for Gameweek {targetGw}...
                </div>
              )}

              <p className="mt-3.5 text-xs font-semibold text-ink-secondary leading-relaxed">
                Evaluated on expected minutes security, underlying threat indices, and fixture strength.
              </p>
            </div>

            <Link
              to="/players"
              className="mt-5 pt-3 border-t border-border flex items-center justify-between text-xs font-black text-stadium-deep hover:text-gold-dark transition-colors"
            >
              <span>Explore All Projected Players</span>
              <ArrowRight size={14} />
            </Link>
          </Card>

          {/* Spotlight 3: Featured Match with Real Probabilities */}
          <Card className="flex flex-col justify-between border-border bg-ivory-surface p-5 shadow-card hover:border-gold-border transition-all">
            <div>
              <div className="flex items-center justify-between mb-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-ivory-subtle border border-border px-3 py-1 text-[10px] font-black uppercase text-ink-primary">
                  <Calendar size={13} className="text-ink-secondary" />
                  Key Fixture
                </span>
                {featuredMatch && (
                  <span className="font-mono text-[10px] font-black uppercase text-gold-dark bg-gold-light px-2 py-0.5 rounded border border-gold-border">
                    {featuredMatch.confidence_level} Conf
                  </span>
                )}
              </div>

              {featuredMatch ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between py-1">
                    <div className="flex items-center gap-2 min-w-0">
                      <TeamBadge team={featuredMatch.home_team} logoUrl={featuredMatch.home_team_logo_url} size="sm" />
                      <span className="font-display font-black text-xs sm:text-sm text-ink-primary truncate">
                        {featuredMatch.home_team}
                      </span>
                    </div>
                    <span className="numeral text-sm font-black text-stadium-deep px-2 py-0.5 rounded bg-ivory-subtle border border-border">
                      {featuredMatch.predicted_scoreline}
                    </span>
                    <div className="flex items-center gap-2 min-w-0 flex-row-reverse sm:flex-row">
                      <span className="font-display font-black text-xs sm:text-sm text-ink-primary truncate">
                        {featuredMatch.away_team}
                      </span>
                      <TeamBadge team={featuredMatch.away_team} logoUrl={featuredMatch.away_team_logo_url} size="sm" />
                    </div>
                  </div>

                  {/* Probability Bar */}
                  <OutcomeProbabilityBar
                    homeTeam={featuredMatch.home_team}
                    awayTeam={featuredMatch.away_team}
                    homeProb={featuredMatch.home_win_probability}
                    drawProb={featuredMatch.draw_probability}
                    awayProb={featuredMatch.away_win_probability}
                    predictedResult={featuredMatch.predicted_result}
                  />
                </div>
              ) : (
                <div className="text-sm font-semibold text-ink-secondary py-3">
                  Match predictions compiling...
                </div>
              )}
            </div>

            <Link
              to="/match-predictions"
              className="mt-5 pt-3 border-t border-border flex items-center justify-between text-xs font-black text-stadium-deep hover:text-gold-dark transition-colors"
            >
              <span>View All Fixture Odds</span>
              <ArrowRight size={14} />
            </Link>
          </Card>
        </div>
      </section>

      {/* Top Projected Scorers — Decision Cards */}
      <section className="space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-black text-ink-primary flex items-center gap-2">
              <Trophy size={24} className="text-gold-metallic" />
              <span>Gameweek {targetGw} Projected Leaders</span>
            </h2>
            <p className="text-sm font-semibold text-ink-secondary mt-1">
              Top predicted point earners rounded to whole numbers for clear, noise-free decisions.
            </p>
          </div>

          <Link to="/players">
            <Button variant="secondary" size="sm" className="gap-1.5 font-bold">
              <span>Full Analytics</span>
              <ArrowRight size={15} />
            </Button>
          </Link>
        </div>

        {topLoading && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <PlayerCardSkeleton key={i} />
            ))}
          </div>
        )}

        {!topLoading && topError && (
          <ErrorState message={topError} onRetry={refetchTop} />
        )}

        {!topLoading && !topError && (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {topPlayers.map((player, idx) => (
              <PlayerCard
                key={player.element ?? player.name ?? idx}
                player={player}
                rank={idx + 1}
                linkToDetail={true}
              />
            ))}
          </div>
        )}
      </section>

      {/* Intelligence & Philosophy Strip */}
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-3 pt-4">
        <Card className="p-6 border border-border bg-ivory-surface">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-stadium-deep text-gold-bright mb-3.5 shadow-sm">
            <Sparkles size={20} />
          </div>
          <h3 className="text-base font-black text-ink-primary mb-1.5">Whole-Number Expected Points</h3>
          <p className="text-xs font-semibold text-ink-secondary leading-relaxed">
            Eliminates statistical illusion. Models factor playing-time probability, finishing form, and opposition defensive structure into honest projections.
          </p>
        </Card>

        <Card className="p-6 border border-border bg-ivory-surface">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gold-light border border-gold-border text-gold-dark mb-3.5 shadow-sm">
            <Shield size={20} />
          </div>
          <h3 className="text-base font-black text-ink-primary mb-1.5">Verified Official Availability</h3>
          <p className="text-xs font-semibold text-ink-secondary leading-relaxed">
            Direct integration with official FPL availability flags and status codes, guaranteeing that injury risks and suspensions are never guessed.
          </p>
        </Card>

        <Card className="p-6 border border-border bg-ivory-surface">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-stadium-forest/15 border border-stadium-forest/30 text-stadium-deep mb-3.5 shadow-sm">
            <TrendingUp size={20} />
          </div>
          <h3 className="text-base font-black text-ink-primary mb-1.5">Three-Outcome Match Models</h3>
          <p className="text-xs font-semibold text-ink-secondary leading-relaxed">
            Simulates every fixture to project home, draw, and away probabilities alongside clean sheet likelihoods for maximum tactical clarity.
          </p>
        </Card>
      </section>
    </div>
  );
}
