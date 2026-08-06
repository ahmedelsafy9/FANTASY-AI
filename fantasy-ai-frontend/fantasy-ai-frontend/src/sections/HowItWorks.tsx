import { motion } from "framer-motion";
import { Database, Cpu, LineChart, Sparkles, Trophy } from "lucide-react";

const STEPS = [
  { icon: Database, title: "Data", desc: "Historical Premier League results, ingested and validated.", color: "text-teal bg-teal/10" },
  { icon: LineChart, title: "Feature Engineering", desc: "Rolling form, fixture context, and price trends derived per player.", color: "text-signal bg-signal/10" },
  { icon: Cpu, title: "Machine Learning", desc: "Multiple models trained and compared on a chronological split.", color: "text-emerald bg-emerald/10" },
  { icon: Sparkles, title: "Prediction", desc: "The best-performing model projects next-Gameweek points.", color: "text-gold bg-gold/10" },
  { icon: Trophy, title: "Fantasy Decision", desc: "You pick, transfer, and captain with an AI-informed edge.", color: "text-gold bg-gold/10" },
];

export function HowItWorks() {
  return (
    <section className="mx-auto max-w-6xl px-5 py-14 lg:px-8">
      <div className="mb-10 text-center">
        <h2 className="font-display text-xl font-bold text-ink sm:text-2xl">How Fantasy-AI Works</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm text-ink-tertiary">
          A real, end-to-end machine learning pipeline — not a black box.
        </p>
      </div>

      <div className="relative grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <div
          className="absolute left-0 right-0 top-8 hidden h-px bg-gradient-to-r from-transparent via-emerald/20 to-transparent lg:block"
          aria-hidden="true"
        />
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: i * 0.08 }}
            className="relative flex flex-col items-center text-center"
          >
            <div className={`z-10 flex h-14 w-14 items-center justify-center rounded-2xl border border-border-soft shadow-card ${step.color}`}>
              <step.icon size={22} />
            </div>
            <h3 className="mt-3 text-sm font-semibold text-ink">{step.title}</h3>
            <p className="mt-1 text-xs leading-relaxed text-ink-tertiary">{step.desc}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
