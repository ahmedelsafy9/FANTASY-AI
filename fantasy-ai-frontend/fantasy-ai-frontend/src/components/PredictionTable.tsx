import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { deriveConfidenceLevel, deriveReasons } from "@/lib/insights";
import { formatStat } from "@/lib/format";
import { getPlayerPrice } from "@/hooks/useSquad";

interface PredictionTableProps {
  players: PlayerRecord[];
  onSelectPlayer: (player: PlayerRecord) => void;
}

export function PredictionTable({ players, onSelectPlayer }: PredictionTableProps) {
  return (
    <div className="overflow-hidden rounded-2xl border border-[#E2E8F0] bg-white shadow-soft">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm border-collapse">
          <thead>
            <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC] text-[11px] font-black uppercase tracking-wider text-[#64748B]">
              <th className="py-3.5 pl-4 pr-2 text-center w-12">#</th>
              <th className="py-3.5 px-3 min-w-[180px]">Player</th>
              <th className="py-3.5 px-3">Pos</th>
              <th className="py-3.5 px-3">Team</th>
              <th className="py-3.5 px-3 text-right">Price</th>
              <th className="py-3.5 px-3 text-right">
                <span className="text-[#059669]">Expected Pts</span>
              </th>
              <th className="py-3.5 px-3 text-center">Confidence</th>
              <th className="py-3.5 px-3 text-right">Form (3 GW)</th>
              <th className="py-3.5 px-3 min-w-[130px]">Key Reason</th>
              <th className="py-3.5 px-3 min-w-[120px]">Next Fixture</th>
              <th className="py-3.5 pr-4 pl-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0]">
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
                  whileHover={{ backgroundColor: "#F8FAFC" }}
                  className="cursor-pointer transition-colors group"
                >
                  {/* Rank */}
                  <td className="py-3 pl-4 pr-2 text-center">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#F1F5F9] text-xs font-mono font-black text-[#334155] group-hover:bg-[#10B981] group-hover:text-white transition-colors">
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
                        className="ring-1 ring-[#10B981]"
                      />
                      <div className="min-w-0">
                        <div className="font-display font-black text-[#0F172A] truncate group-hover:text-[#059669] transition-colors">
                          {p.name ?? "N/A"}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Position */}
                  <td className="py-3 px-3">
                    <span className="rounded-full bg-[#F1F5F9] border border-[#CBD5E1] px-2 py-0.5 text-[10px] font-black uppercase text-[#334155]">
                      {p.position === "GKP" ? "GK" : p.position ?? "-"}
                    </span>
                  </td>

                  {/* Team */}
                  <td className="py-3 px-3">
                    <TeamBadge team={p.team} logoUrl={p.team_logo_url} size="sm" showName />
                  </td>

                  {/* Price */}
                  <td className="py-3 px-3 text-right font-mono font-bold text-[#0F172A]">
                    £{price.toFixed(1)}m
                  </td>

                  {/* Expected Points */}
                  <td className="py-3 px-3 text-right">
                    <span className="inline-block rounded-lg bg-[#ECFDF5] px-2.5 py-1 font-mono font-black text-[#059669] border border-[#A7F3D0]">
                      {formatStat(expectedPoints)} pts
                    </span>
                  </td>

                  {/* Confidence */}
                  <td className="py-3 px-3 text-center">
                    <ConfidenceBadge level={confidence} showTooltip={false} />
                  </td>

                  {/* Form */}
                  <td className="py-3 px-3 text-right font-mono font-bold text-[#475569]">
                    {typeof p.total_points_avg_last_3 === "number"
                      ? formatStat(p.total_points_avg_last_3)
                      : "—"}
                  </td>

                  {/* Top Reason */}
                  <td className="py-3 px-3">
                    {topReason ? (
                      <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#475569]">
                        <span>{topReason.icon}</span>
                        <span className="truncate max-w-[130px]">{topReason.text}</span>
                      </span>
                    ) : (
                      <span className="text-[#94A3B8] text-xs">—</span>
                    )}
                  </td>

                  {/* Upcoming fixture */}
                  <td className="py-3 px-3">
                    <UpcomingFixtures player={p} variant="compact" maxFixtures={1} />
                  </td>

                  {/* Arrow */}
                  <td className="py-3 pr-4 pl-2 text-right">
                    <ChevronRight size={16} className="text-[#94A3B8] group-hover:text-[#059669] transition-colors inline-block" />
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
