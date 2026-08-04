import { motion } from "framer-motion";
import { Trophy } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { formatStat } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PredictionRankProps {
  players: PlayerRecord[];
  onSelect?: (player: PlayerRecord) => void;
}

/** A ranked leaderboard for the Top AI Picks — rank #1 is visually distinguished,
 * not with a childish trophy sticker, but with size, color, and elevation. */
export function PredictionRank({ players, onSelect }: PredictionRankProps) {
  return (
    <ol className="flex flex-col gap-2">
      {players.map((player, index) => {
        const rank = index + 1;
        const isTop = rank === 1;
        return (
          <motion.li
            key={player.element ?? player.name ?? index}
            initial={{ opacity: 0, x: -12 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, margin: "-20px" }}
            transition={{ duration: 0.4, delay: index * 0.04, ease: [0.16, 1, 0.3, 1] }}
          >
            <button
              onClick={() => onSelect?.(player)}
              className={cn(
                "flex w-full items-center gap-4 rounded-xl border px-4 py-3 text-left transition-all duration-200",
                isTop
                  ? "border-gold/30 bg-gradient-to-r from-gold/10 via-surface to-surface shadow-glow"
                  : "border-border-soft bg-surface hover:border-border-medium hover:bg-surface-hover",
              )}
            >
              <div
                className={cn(
                  "flex w-8 shrink-0 items-center justify-center font-mono text-sm font-bold",
                  isTop ? "text-gold text-lg" : "text-ink-tertiary",
                )}
              >
                {isTop ? <Trophy size={18} className="text-gold" /> : String(rank).padStart(2, "0")}
              </div>

              <PlayerAvatar name={player.name} size={isTop ? "md" : "sm"} />

              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-ink">
                  {player.name ?? "Unknown player"}
                </div>
                <div className="mt-0.5">
                  <TeamBadge team={player.team} size="sm" showName />
                </div>
              </div>

              <div className="shrink-0 text-right">
                <div
                  className={cn(
                    "numeral font-bold leading-none",
                    isTop ? "text-2xl text-gold" : "text-lg text-ink",
                  )}
                >
                  {formatStat(player.predicted_total_points)}
                </div>
                <div className="mt-0.5 text-[10px] uppercase tracking-wide text-ink-tertiary">
                  xPts
                </div>
              </div>
            </button>
          </motion.li>
        );
      })}
    </ol>
  );
}
