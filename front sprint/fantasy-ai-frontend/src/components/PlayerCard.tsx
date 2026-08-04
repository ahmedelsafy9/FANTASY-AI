import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { Stat, ConfidenceBar } from "@/components/stats";
import { Badge } from "@/components/ui/primitives";
import { formatPrice, formatStat } from "@/lib/format";
import { derivePlayingTimeReliability } from "@/lib/insights";
import { cn } from "@/lib/utils";

interface PlayerCardProps {
  player: PlayerRecord;
  rank?: number;
  onClick?: () => void;
  className?: string;
}

/**
 * The primary card used across Predictions/Players/Dashboard. Predicted
 * points is the dominant visual element by design (large mono numeral,
 * gold). Every field is rendered defensively — "N/A" or omitted when the
 * backend didn't provide it, never fabricated.
 */
export function PlayerCard({ player, rank, onClick, className }: PlayerCardProps) {
  const predicted = player.predicted_total_points;
  const reliability = derivePlayingTimeReliability(player);
  const hasFixture = Boolean(player.opponent_team);

  return (
    <motion.article
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-40px" }}
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => {
        if (onClick && (e.key === "Enter" || e.key === " ")) onClick();
      }}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-2xl border border-border-soft bg-surface shadow-card transition-all duration-250",
        onClick && "cursor-pointer hover:border-gold/30 hover:bg-surface-hover hover:-translate-y-0.5",
        className,
      )}
    >
      {typeof rank === "number" && (
        <div className="absolute left-4 top-4 font-mono text-xs font-semibold text-ink-tertiary">
          {String(rank).padStart(2, "0")}
        </div>
      )}

      <div className="flex items-start justify-between gap-4 border-b border-border-soft p-5 pl-14">
        <div className="flex items-center gap-3">
          <PlayerAvatar name={player.name} size="md" />
          <div>
            <h3 className="font-display text-base font-semibold text-ink">
              {player.name ?? "Unknown player"}
            </h3>
            <div className="mt-1 flex items-center gap-2">
              <TeamBadge team={player.team} size="sm" />
              {player.position && (
                <span className="text-xs text-ink-tertiary">{player.position}</span>
              )}
            </div>
          </div>
        </div>
        <Sparkles size={16} className="mt-1 shrink-0 text-signal opacity-70" aria-hidden="true" />
      </div>

      <div className="flex items-center justify-between gap-4 p-5">
        <div>
          <span className="text-[11px] uppercase tracking-wide text-ink-tertiary">
            Expected Points
          </span>
          <div className="numeral text-gradient-gold mt-0.5 text-4xl font-bold leading-none">
            {formatStat(predicted)}
          </div>
        </div>

        <div className="flex flex-col items-end gap-1 text-right">
          {hasFixture ? (
            <span className="text-sm text-ink-secondary">
              {player.team ? "vs" : ""} {player.opponent_team}
              {player.is_home === 0 && <span className="text-ink-tertiary"> (A)</span>}
              {player.is_home === 1 && <span className="text-ink-tertiary"> (H)</span>}
            </span>
          ) : (
            <span className="text-sm text-ink-tertiary">Fixture N/A</span>
          )}
          {typeof player.predicted_for_gw === "number" && (
            <Badge tone="signal">GW {player.predicted_for_gw}</Badge>
          )}
        </div>
      </div>

      <div className="px-5 pb-4">
        <ConfidenceBar value={reliability} label={reliability !== null ? undefined : "RELIABILITY N/A"} />
      </div>

      <div className="grid grid-cols-3 gap-2 border-t border-border-soft p-5">
        <Stat label="Form (3gw)" value={formatStat(player.total_points_avg_last_3)} tone="gold" />
        <Stat label="Minutes" value={formatStat(player.minutes_avg_last_5, 0)} tone="signal" />
        <Stat label="Price" value={formatPrice(player.value)} />
      </div>
    </motion.article>
  );
}
