import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowRight, Shield, Crown } from "lucide-react";
import { Button } from "@/components/ui/primitives";
import { GameweekBadge } from "@/components/GameweekBadge";

interface HeroProps {
  gameweek: number | null | undefined;
  modelName?: string | null;
}

const FLOATING_STATS = [
  { label: "xPts", value: "8.7", top: "18%", left: "8%", delay: 0 },
  { label: "Form", value: "7.9", top: "62%", left: "5%", delay: 1.2 },
  { label: "FDR", value: "2", top: "30%", left: "88%", delay: 0.6 },
  { label: "xG", value: "0.61", top: "70%", left: "90%", delay: 1.8 },
];

export function Hero({ gameweek, modelName }: HeroProps) {
  return (
    <section className="relative overflow-hidden border-b border-border-soft">
      {/* Football pitch-inspired background */}
      <div
        className="absolute inset-0 h-[600px] opacity-40"
        style={{
          background: "radial-gradient(ellipse 120% 80% at 50% 30%, rgba(16,185,129,0.12) 0%, transparent 60%)",
        }}
        aria-hidden="true"
      />
      <div className="pitch-grid absolute inset-0 h-[600px]" aria-hidden="true" />
      <div className="absolute inset-x-0 top-0 h-[600px] bg-grid-fade" aria-hidden="true" />

      {/* Floating data fragments */}
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

      <div className="relative mx-auto flex max-w-5xl flex-col items-center px-6 pb-20 pt-16 text-center lg:pt-24">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-5 inline-flex items-center gap-2 rounded-full border border-emerald/20 bg-emerald/[0.06] px-4 py-1.5 text-xs font-medium text-emerald"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-emerald animate-pulse-soft" />
          {modelName ? `Live model: ${modelName}` : "AI-powered FPL intelligence"}
        </motion.div>

        <motion.h1
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="text-4xl font-bold leading-[1.08] tracking-tight text-ink sm:text-5xl lg:text-6xl"
        >
          Your AI-powered
          <br />
          <span className="text-gradient-emerald">Fantasy Manager.</span>
        </motion.h1>

        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="mt-5 max-w-lg text-balance text-base text-ink-secondary sm:text-lg"
        >
          Scout players, build squads, pick captains — all backed by real
          machine learning predictions trained on Premier League data.
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="mt-8 flex flex-col items-center gap-4 sm:flex-row"
        >
          <GameweekBadge gameweek={gameweek} />
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.4, ease: [0.16, 1, 0.3, 1] }}
          className="mt-8 flex flex-wrap items-center justify-center gap-3"
        >
          <Link to="/predictions">
            <Button size="lg">
              View Predictions <ArrowRight size={16} />
            </Button>
          </Link>
          <Link to="/squad">
            <Button variant="secondary" size="lg">
              <Shield size={16} /> Build Squad
            </Button>
          </Link>
          <Link to="/captain">
            <Button variant="ghost" size="lg">
              <Crown size={16} /> Captain Pick
            </Button>
          </Link>
        </motion.div>
      </div>
    </section>
  );
}
