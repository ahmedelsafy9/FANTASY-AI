import { motion } from "framer-motion";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { FDRBadge } from "@/components/FDRBadge";
import { formatPrice, formatStat, formatInt } from "@/lib/format";
import { cn } from "@/lib/utils";

interface PredictionRankProps {
  players: PlayerRecord[];
  onSelect: (player: PlayerRecord) => void;
}

/**
 * A ranked leaderboard of players, ordered by predicted points.
 * Sport-style rank row with player identity, fixture, and whole-number prediction.
 */
export function PredictionRank({ players, onSelect }: PredictionRankProps) {
  return (
    <div className="flex flex-col gap-2">
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
              "group flex items-center gap-3 rounded-xl border px-4 py-3 text-left transition-all cursor-pointer shadow-xs",
              isTop3
                ? "border-[#E5D08E] bg-[#FDF8EC] hover:border-[#B58A18] hover:bg-[#FBF4E4]"
                : "border-[#E8E3ED] bg-white hover:border-[#7041C5] hover:bg-[#F8F7FA]",
            )}
          >
            {/* Rank */}
            <div
              className={cn(
                "flex h-7 w-7 shrink-0 items-center justify-center rounded-lg font-mono text-xs font-black shadow-xs",
                isTop3
                  ? "bg-[#B58A18] text-white"
                  : "bg-[#EEE7FA] text-[#452477]",
              )}
            >
              {rank}
            </div>

            {/* Player */}
            <PlayerAvatar name={player.name} photoUrl={player.photo_url} size="md" />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="truncate text-sm font-black text-[#19171D] group-hover:text-[#7041C5] transition-colors">
                  {player.name ?? "N/A"}
                </span>
                {player.position && (
                  <span className="hidden rounded bg-[#452477] px-1.5 py-0.5 text-[9px] font-black uppercase text-white sm:inline">
                    {player.position}
                  </span>
                )}
              </div>
              <div className="mt-0.5 flex items-center gap-2">
                <TeamBadge team={player.team} logoUrl={player.team_logo_url} size="sm" />
                <span className="hidden text-xs font-bold text-[#6F6A76] sm:inline">
                  {player.team ?? ""}
                </span>
              </div>
            </div>

            {/* Fixture + FDR */}
            <div className="hidden flex-col items-end gap-0.5 sm:flex">
              {player.opponent_team && (
                <span className="text-xs font-bold text-[#6F6A76]">
                  vs {player.opponent_team}
                  {player.is_home === 1 ? " (H)" : player.is_home === 0 ? " (A)" : ""}
                </span>
              )}
              <FDRBadge difficulty={player.fixture_difficulty} size="sm" />
            </div>

            {/* Stats */}
            <div className="hidden flex-col items-end gap-0.5 md:flex">
              <span className="numeral text-xs font-bold text-[#6F6A76]">
                Form {formatStat(player.total_points_avg_last_3)}
              </span>
              <span className="numeral text-xs font-bold text-[#6F6A76]">
                {formatPrice(player.value)}
              </span>
            </div>

            {/* Predicted points */}
            <div className="shrink-0 text-right">
              <span className="text-[8px] font-black uppercase tracking-widest text-[#6F6A76] block">
                xPts
              </span>
              <div
                className={cn(
                  "numeral text-xl font-black leading-none",
                  isTop3 ? "text-[#8C680E]" : "text-[#7041C5]",
                )}
              >
                {formatInt(player.predicted_total_points)}
              </div>
            </div>
          </motion.button>
        );
      })}
    </div>
  );
}
