import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { LowOwnershipBadge } from "@/components/LowOwnershipBadge";
import { deriveConfidenceLevel, deriveReasons } from "@/lib/insights";
import { formatStat } from "@/lib/format";
import { getPlayerPrice } from "@/hooks/useSquad";

interface PredictionTableProps {
  players: PlayerRecord[];
  onSelectPlayer: (player: PlayerRecord) => void;
}

export function PredictionTable({ players, onSelectPlayer }: PredictionTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-[#E8E3ED] bg-white shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-[#E8E3ED] bg-[#F8F7FA] text-[11px] font-black uppercase tracking-wider text-[#6F6A76]">
              <th className="py-3.5 pl-4 pr-2 text-center w-12">#</th>
              <th className="py-3.5 px-3 min-w-[180px]">Player</th>
              <th className="py-3.5 px-3">Pos</th>
              <th className="py-3.5 px-3">Team</th>
              <th className="py-3.5 px-3 text-right">Price</th>
              <th className="py-3.5 px-3 text-right">
                <span className="text-[#7041C5]">Expected Pts</span>
              </th>
              <th className="py-3.5 px-3 text-center">Confidence</th>
              <th className="py-3.5 px-3 text-right">Form (3 GW)</th>
              <th className="py-3.5 px-3 min-w-[130px]">Key Reason</th>
              <th className="py-3.5 px-3 min-w-[120px]">Next Fixture</th>
              <th className="py-3.5 pr-4 pl-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E8E3ED]">
            {players.map((p, idx) => {
              const price = getPlayerPrice(p);
              const expectedPoints = p.predicted_expected_points ?? p.predicted_total_points;
              const confidence = deriveConfidenceLevel(p);
              const reasons = deriveReasons(p);
              const topReason = reasons[0];

              return (
                <motion.tr
                  key={p.element ?? p.name ?? idx}
                  onClick={() => onSelectPlayer(p)}
                  whileHover={{ backgroundColor: "#F8F7FA" }}
                  className="cursor-pointer transition-colors group"
                >
                  {/* Rank */}
                  <td className="py-3 pl-4 pr-2 text-center">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#F4F3F6] text-xs font-mono font-black text-[#19171D] group-hover:bg-[#7041C5] group-hover:text-white transition-colors">
                      {idx + 1}
                    </span>
                  </td>

                  {/* Player info */}
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-3">
                      <PlayerAvatar
                        name={p.name}
                        photoUrl={p.photo_url}
                        size="sm"
                        className="ring-1 ring-[#7041C5]/30"
                      />
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-display font-black text-[#19171D] truncate group-hover:text-[#7041C5] transition-colors">
                            {p.name ?? "N/A"}
                          </span>
                          <LowOwnershipBadge
                            ownership={p.selected_by_percent ?? (p as Record<string, unknown>).ownership_pct as number | undefined}
                            predictedPoints={expectedPoints}
                            showLabel={false}
                          />
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Position */}
                  <td className="py-3 px-3">
                    <span className="rounded-full bg-[#EEE7FA] border border-[#D4C3ED] px-2 py-0.5 text-[10px] font-black uppercase text-[#452477]">
                      {p.position === "GKP" ? "GK" : p.position ?? "-"}
                    </span>
                  </td>

                  {/* Team */}
                  <td className="py-3 px-3">
                    <TeamBadge team={p.team} logoUrl={p.team_logo_url} size="sm" showName />
                  </td>

                  {/* Price */}
                  <td className="py-3 px-3 text-right font-mono font-bold text-[#19171D]">
                    £{price.toFixed(1)}m
                  </td>

                  {/* Expected Points */}
                  <td className="py-3 px-3 text-right">
                    <span className="inline-block rounded-lg bg-[#EEE7FA] px-2.5 py-1 font-mono font-black text-[#452477] border border-[#D4C3ED]">
                      {formatStat(expectedPoints)} pts
                    </span>
                  </td>

                  {/* Confidence */}
                  <td className="py-3 px-3 text-center">
                    <ConfidenceBadge level={confidence} showTooltip={false} />
                  </td>

                  {/* Form */}
                  <td className="py-3 px-3 text-right font-mono font-bold text-[#6F6A76]">
                    {typeof p.total_points_avg_last_3 === "number"
                      ? formatStat(p.total_points_avg_last_3)
                      : "—"}
                  </td>

                  {/* Top Reason */}
                  <td className="py-3 px-3">
                    {topReason ? (
                      <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#6F6A76]">
                        <span>{topReason.icon}</span>
                        <span className="truncate max-w-[130px]">{topReason.text}</span>
                      </span>
                    ) : (
                      <span className="text-[#6F6A76] text-xs">—</span>
                    )}
                  </td>

                  {/* Upcoming fixture */}
                  <td className="py-3 px-3">
                    <UpcomingFixtures player={p} variant="compact" maxFixtures={1} />
                  </td>

                  {/* Arrow */}
                  <td className="py-3 pr-4 pl-2 text-right">
                    <ChevronRight size={16} className="text-[#6F6A76] group-hover:text-[#7041C5] transition-colors inline-block" />
                  </td>
                </motion.tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
