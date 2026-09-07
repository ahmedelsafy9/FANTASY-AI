import { motion } from "framer-motion";
import { ChevronRight } from "lucide-react";
import type { PlayerRecord } from "@/types/api";
import { PlayerAvatar, TeamBadge } from "@/components/identity";
import { UpcomingFixtures } from "@/components/UpcomingFixtures";
import { formatStat } from "@/lib/format";
import { getPlayerPrice } from "@/hooks/useSquad";

interface PredictionTableProps {
  players: PlayerRecord[];
  onSelectPlayer: (player: PlayerRecord) => void;
}

export function PredictionTable({ players, onSelectPlayer }: PredictionTableProps) {
  return (
    <div className="overflow-hidden rounded-chunky-xl border border-[#E2E8F0] bg-white shadow-card">
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
                <span className="text-[#92400E]">AI xPts</span>
              </th>
              <th className="py-3.5 px-3 text-right">
                <span className="text-amber-800">Rank Score</span>
              </th>
              <th className="py-3.5 px-3 text-center">P(≥6)</th>
              <th className="py-3.5 px-3 text-center">P(≥10)</th>
              <th className="py-3.5 px-3 text-right">P85 Ceiling</th>
              <th className="py-3.5 px-3 min-w-[130px]">Next Fixture</th>
              <th className="py-3.5 pr-4 pl-2 text-right"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[#E2E8F0]">
            {players.map((p, idx) => {
              const price = getPlayerPrice(p);
              const rankScore = p.predicted_fpl_rank_score;
              const expectedPoints = p.predicted_expected_points ?? p.predicted_total_points;
              const p6 = typeof p.prob_high_score_6 === "number" ? Math.round(p.prob_high_score_6 * 100) : null;
              const p10 = typeof p.prob_high_score_10 === "number" ? Math.round(p.prob_high_score_10 * 100) : null;
              const ceiling = p.ceiling_p85 ?? p.predicted_p85_points;

              return (
                <motion.tr
                  key={p.element ?? p.name ?? idx}
                  onClick={() => onSelectPlayer(p)}
                  whileHover={{ backgroundColor: "#F8FAFC" }}
                  className="cursor-pointer transition-colors group"
                >
                  {/* Rank */}
                  <td className="py-3 pl-4 pr-2 text-center">
                    <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-[#F1F5F9] text-xs font-mono font-black text-[#334155] group-hover:bg-[#F59E0B] group-hover:text-white transition-colors">
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
                        {p.prediction_signals?.recent_form?.rating && (
                          <span className="text-[10px] font-bold text-[#64748B]">
                            {p.prediction_signals.recent_form.rating} Form
                          </span>
                        )}
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

                  {/* AI xPts */}
                  <td className="py-3 px-3 text-right">
                    <span className="inline-block rounded-lg bg-[#FFFBEB] px-2 py-1 font-mono font-black text-[#92400E] border border-[#FDE68A]">
                      {formatStat(expectedPoints)}
                    </span>
                  </td>

                  {/* Rank Score */}
                  <td className="py-3 px-3 text-right font-mono font-black text-[#0F172A]">
                    {typeof rankScore === "number" ? formatStat(rankScore) : "-"}
                  </td>

                  {/* P(>=6) */}
                  <td className="py-3 px-3 text-center">
                    {p6 !== null ? (
                      <span className="font-mono font-black text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 text-xs">
                        {p6}%
                      </span>
                    ) : (
                      <span className="text-[#94A3B8]">-</span>
                    )}
                  </td>

                  {/* P(>=10) */}
                  <td className="py-3 px-3 text-center">
                    {p10 !== null ? (
                      <span className="font-mono font-black text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200 text-xs">
                        {p10}%
                      </span>
                    ) : (
                      <span className="text-[#94A3B8]">-</span>
                    )}
                  </td>

                  {/* P85 Ceiling */}
                  <td className="py-3 px-3 text-right font-mono font-black text-purple-700">
                    {typeof ceiling === "number" ? formatStat(ceiling) : "-"}
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
