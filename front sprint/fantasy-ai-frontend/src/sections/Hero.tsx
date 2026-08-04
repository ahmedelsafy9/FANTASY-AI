import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowRight, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { GameweekBadge } from "@/components/GameweekBadge";

interface HeroProps {
  gameweek: number | null | undefined;
  modelName?: string | null;
}

const FLOATING_STATS = [
  { label: "xPts", value: "8.7", top: "18%", left: "8%", delay: 0 },
  { label: "Form", value: "7.9", top: "62%", left: "5%", delay: 1.2 },
  { label: "xG", value: "0.61", top: "30%", left: "88%", delay: 0.6 },
  { label: "Mins", value: "90", top: "70%", left: "90%", delay: 1.8 },
];

export function Hero({ gameweek, modelName }: HeroProps) {
  return (
    <section className="relative overflow-hidden border-b border-border-soft">
      {/* Ambient signature texture: broadcast-angle pitch grid, not cyberpunk */}
      <div className="pitch-grid absolute inset-0 h-[640px]" aria-hidden="true" />
      <div className="absolute inset-x-0 top-0 h-[640px] bg-grid-fade" aria-hidden="true" />

      {/* Floating data fragments — subtle, sparse, professional */}
      {FLOATING_STATS.map((s) => (
        <motion.div
          key={s.label}
          className="glass absolute hidden rounded-xl border border-border-soft px-3 py-2 lg:block"
          style={{ top: s.top, left: s.left }}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1, y: [0, -14, 0] }}
          transition={{
            opacity: { duration: 1, delay: s.delay },
            y: { duration: 8, repeat: Infinity, ease: "easeInOut", delay: s.delay },
          }}
          aria-hidden="true"
        >
          <div className="text-[10px] uppercase tracking-wide text-ink-tertiary">{s.label}</div>
          <div className="numeral text-sm font-semibold text-ink">{s.value}</div>
        </motion.div>
      ))}

      <div className="relative mx-auto flex max-w-5xl flex-col items-center px-6 pb-24 pt-20 text-center lg:pt-28">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-6 inline-flex items-center gap-2 rounded-full border border-border-medium bg-surface px-4 py-1.5 text-xs font-medium text-ink-secondary"
        >
          <TrendingUp size={13} className="text-teal" />
          {modelName ? `Live model: ${modelName}` : "AI-powered FPL intelligence"}
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-5xl font-bold leading-[1.05] tracking-tight text-ink sm:text-6xl lg:text-7xl"
        >
          Predict the players.
          <br />
          <span className="text-gradient-gold">Build the advantage.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="mt-6 max-w-xl text-balance text-lg text-ink-secondary"
        >
          Fantasy-AI trains real machine learning models on historical Premier
          League data to project every player's expected points for the next
          Gameweek.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="mt-10 flex flex-col items-center gap-5"
        >
          <GameweekBadge gameweek={gameweek} />
          <Link to="/predictions">
            <Button size="lg">
              Explore Predictions <ArrowRight size={16} />
            </Button>
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
