import { motion } from "framer-motion";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { FixtureBadge } from "@/components/FixtureBadge";
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
  const isHighValue = typeof predicted === "number" && predicted >= 7;

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
        "group relative flex flex-col overflow-hidden rounded-xl border border-border-soft bg-surface shadow-card transition-all duration-200",
        onClick && "cursor-pointer hover:border-emerald/25 hover:shadow-card-hover hover:-translate-y-0.5",
        isHighValue && "border-gold/15",
        className,
      )}
    >
      {/* Top accent stripe */}
      <div
        className={cn(
          "h-0.5 w-full",
          isHighValue
            ? "bg-gradient-to-r from-gold/60 via-gold/30 to-transparent"
            : "bg-gradient-to-r from-emerald/40 via-emerald/15 to-transparent",
        )}
      />

      {/* Header: Player identity */}
      <div className="flex items-start gap-3 p-4 pb-3">
        {/* Rank badge */}
        {typeof rank === "number" && (
          <div
            className={cn(
              "flex h-6 w-6 shrink-0 items-center justify-center rounded-md font-mono text-[11px] font-bold",
              rank <= 3
                ? "bg-gold/15 text-gold"
                : "bg-white/5 text-ink-tertiary",
            )}
          >
            {rank}
          </div>
        )}

        {/* Player photo — larger, more prominent */}
        <PlayerAvatar
          name={player.name}
          photoUrl={player.photo_url}
          size="lg"
          className={cn(
            "shrink-0 transition-transform duration-200",
            onClick && "group-hover:scale-105",
          )}
        />

        <div className="min-w-0 flex-1">
          <h3 className="font-display text-[15px] font-semibold leading-tight text-ink truncate">
            {player.name ?? "Unknown player"}
          </h3>
          <div className="mt-1.5 flex items-center gap-2">
            <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" />
            {player.position && (
              <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] font-semibold uppercase text-ink-tertiary">
                {player.position}
              </span>
            )}
          </div>
        </div>

        {/* Predicted points — dominant element */}
        <div className="shrink-0 text-right">
          <span className="text-[9px] font-medium uppercase tracking-widest text-ink-tertiary">
            xPts
          </span>
          <div
            className={cn(
              "numeral text-gradient-gold text-3xl font-bold leading-none",
              isHighValue && "drop-shadow-[0_0_16px_rgba(232,184,92,0.25)]",
            )}
          >
            {formatStat(predicted)}
          </div>
        </div>
      </div>

      {/* Fixture + GW row */}
      <div className="flex items-center justify-between gap-2 border-t border-border-soft px-4 py-2.5">
        <FixtureBadge player={player} size="sm" />
        <div className="flex items-center gap-1.5">
          {typeof player.predicted_for_gw === "number" && (
            <Badge tone="signal">GW {player.predicted_for_gw}</Badge>
          )}
        </div>
      </div>

      {/* Stats footer */}
      <div className="grid grid-cols-3 gap-px border-t border-border-soft bg-border-soft">
        <StatCell label="Form" value={formatStat(player.total_points_avg_last_3)} />
        <StatCell
          label="Minutes"
          value={formatStat(player.minutes_avg_last_5, 0)}
          bar={reliability}
        />
        <StatCell label="Price" value={formatPrice(player.value)} />
      </div>
    </motion.article>
  );
}

function StatCell({
  label,
  value,
  bar,
}: {
  label: string;
  value: string;
  bar?: number | null;
}) {
  return (
    <div className="flex flex-col gap-1 bg-surface px-3 py-2.5">
      <span className="text-[9px] font-medium uppercase tracking-wider text-ink-tertiary">
        {label}
      </span>
      <span className="numeral text-sm font-semibold text-ink">{value}</span>
      {bar !== undefined && bar !== null && (
        <div className="mt-0.5 h-1 w-full overflow-hidden rounded-full bg-white/[0.06]">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-700",
              bar >= 0.75 ? "bg-emerald" : bar >= 0.5 ? "bg-gold" : "bg-coral",
            )}
            style={{ width: `${Math.max(0, Math.min(1, bar)) * 100}%` }}
          />
        </div>
      )}
    </div>
  );
}
