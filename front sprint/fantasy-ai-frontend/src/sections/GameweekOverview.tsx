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
    },
    {
      icon: Cpu,
      label: "Active model",
      value: health?.model_name ?? "N/A",
    },
    {
      icon: Users,
      label: "Players tracked",
      value: typeof health?.player_count === "number" ? health.player_count.toLocaleString() : "N/A",
    },
  ];

  return (
    <section className="mx-auto max-w-7xl px-5 py-10 lg:px-8">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        {items.map((item, i) => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: i * 0.06 }}
            className="flex items-center gap-4 rounded-2xl border border-border-soft bg-surface px-5 py-4"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-signal/10 text-signal">
              <item.icon size={18} />
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wide text-ink-tertiary">
                {item.label}
              </div>
              <div className="numeral text-lg font-semibold text-ink">{item.value}</div>
            </div>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
