import { motion } from "framer-motion";
import { Activity, Cpu, Users } from "lucide-react";
import type { HealthResponse } from "@/types/api";

interface GameweekOverviewProps {
  health: HealthResponse | null;
  gameweek: number | null | undefined;
}

export function GameweekOverview({ health, gameweek }: GameweekOverviewProps) {
  const items = [
    {
      icon: Activity,
      label: "Upcoming Gameweek",
      value: typeof gameweek === "number" ? `GW ${gameweek}` : "N/A",
      color: "text-[#059669] bg-[#ECFDF5]",
    },
    {
      icon: Cpu,
      label: "Active Model",
      value: health?.model_name ?? "N/A",
      color: "text-[#92400E] bg-[#FFFBEB]",
    },
    {
      icon: Users,
      label: "Players Tracked",
      value: typeof health?.player_count === "number" ? health.player_count.toLocaleString() : "N/A",
      color: "text-indigo-600 bg-indigo-100",
    },
  ];

  return (
    <section className="mx-auto max-w-7xl px-4 py-6 lg:px-8">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {items.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.06 }}
            className="flex items-center gap-3.5 rounded-chunky-lg border border-[#E2E8F0] bg-white p-4 shadow-card"
          >
            <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl font-bold ${item.color}`}>
              <item.icon size={18} />
            </div>
            <div>
              <div className="text-[10px] font-black uppercase tracking-wider text-[#64748B]">
                {item.label}
              </div>
              <div className="numeral text-base font-black text-[#0F172A]">{item.value}</div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
