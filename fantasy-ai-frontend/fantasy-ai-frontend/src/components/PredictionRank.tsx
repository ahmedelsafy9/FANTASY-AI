import { motion } from "framer-motion";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { FDRBadge } from "@/components/FDRBadge";
import { formatPrice, formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PredictionRankProps {
  players: PlayerRecord[];
  onSelect: (player: PlayerRecord) => void;
}

/**
 * A ranked leaderboard of players, ordered by predicted points. Used on
 * the Home page "Top AI Picks" section. Each row is a compact,
 * sport-style rank row with player identity, fixture, and prediction.
 */
export function PredictionRank({ players, onSelect }: PredictionRankProps) {
  return (
    <div className="flex flex-col gap-1.5">
      {players.map((player, i) => {
        const rank = i + 1;
        const isTop3 = rank <= 3;

        return (
          <motion.button
            key={player.element ?? player.name ?? i}
            initial={{ opacity: 0, x: -8 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.35, delay: i * 0.04 }}
            onClick={() => onSelect(player)}
            className={cn(
              "group flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all",
              isTop3
                ? "border-gold/10 bg-gold/[0.03] hover:border-gold/20 hover:bg-gold/[0.06]"
                : "border-border-soft bg-surface hover:border-emerald/15 hover:bg-surface-hover",
            )}
          >
            {/* Rank */}
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg font-mono text-xs font-bold",
                isTop3 ? "bg-gold/15 text-gold" : "bg-white/5 text-ink-tertiary",
              )}
            >
              {rank}
            </div>

            {/* Player */}
            <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="md" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-semibold text-ink">{player.name ?? "N/A"}</span>
                {player.position && (
                  <span className="hidden rounded bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-ink-tertiary sm:inline">
                    {player.position}
                  </span>
                )}
              </div>
              <div className="mt-0.5 flex items-center gap-2">
                <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" />
                <span className="hidden text-xs text-ink-tertiary sm:inline">
                  {player.team ?? ""}
                </span>
              </div>
            </div>

            {/* Fixture + FDR */}
            <div className="hidden flex-col items-end gap-0.5 sm:flex">
              {player.opponent_team && (
                <span className="text-xs text-ink-secondary">
                  vs {player.opponent_team}
                  {player.is_home === 1 ? " (H)" : player.is_home === 0 ? " (A)" : ""}
                </span>
              )}
              <FDRBadge difficulty={player.fixture_difficulty} size="sm" />
            </div>

            {/* Stats */}
            <div className="hidden flex-col items-end gap-0.5 md:flex">
              <span className="numeral text-xs text-ink-tertiary">
                Form {formatStat(player.total_points_avg_last_3)}
              </span>
              <span className="numeral text-xs text-ink-tertiary">
                {formatPrice(player.value)}
              </span>
            </div>

            {/* Predicted points */}
            <div className="shrink-0 text-right">
              <span className="text-[8px] font-medium uppercase tracking-widest text-ink-tertiary">
                xPts
              </span>
              <div
                className={cn(
                  "numeral text-xl font-bold leading-none",
                  isTop3 ? "text-gradient-gold" : "text-ink",
                )}
              >
                {formatStat(player.predicted_total_points)}
              </div>
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}
