import { motion } from "framer-motion";
import { Activity, Cpu, Users } from "lucide-react";
import type { HealthResponse } from "@/types/api";

interface GameweekOverviewProps {
  health: HealthResponse | null;
  gameweek: number | null | undefined;
}

/** A compact "command center" strip summarizing live system + Gameweek state. */
export function GameweekOverview({ health, gameweek }: GameweekOverviewProps) {
  const items = [
    {
      icon: Activity,
      label: "Upcoming Gameweek",
      value: typeof gameweek === "number" ? `GW ${gameweek}` : "N/A",
      color: "text-emerald bg-emerald/10",
    },
    {
      icon: Cpu,
      label: "Active model",
      value: health?.model_name ?? "N/A",
      color: "text-gold bg-gold/10",
    },
    {
      icon: Users,
      label: "Players tracked",
      value: typeof health?.player_count === "number" ? health.player_count.toLocaleString() : "N/A",
      color: "text-signal bg-signal/10",
    },
  ];

  return (
    <section className="mx-auto max-w-7xl px-5 py-8 lg:px-8">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {items.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.06 }}
            className="flex items-center gap-3 rounded-xl border border-border-soft bg-surface px-4 py-3"
          >
            <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${item.color}`}>
              <item.icon size={16} />
            </div>
            <div>
              <div className="text-[10px] font-medium uppercase tracking-wider text-ink-tertiary">
                {item.label}
              </div>
              <div className="numeral text-base font-semibold text-ink">{item.value}</div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
