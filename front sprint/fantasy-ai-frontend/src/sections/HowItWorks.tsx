import { motion } from "framer-motion";
import { Database, Cpu, LineChart, Sparkles, Trophy } from "lucide-react";

const STEPS = [
  { icon: Database, title: "Data", desc: "Historical Premier League results, ingested and validated." },
  { icon: LineChart, title: "Feature Engineering", desc: "Rolling form, fixture context, and price trends derived per player." },
  { icon: Cpu, title: "Machine Learning", desc: "Multiple models trained and compared on a chronological split." },
  { icon: Sparkles, title: "Prediction", desc: "The best-performing model projects next-Gameweek points." },
  { icon: Trophy, title: "Fantasy Decision", desc: "You pick, transfer, and captain with an AI-informed edge." },
];

export function HowItWorks() {
  return (
    <section className="mx-auto max-w-6xl px-5 py-16 lg:px-8">
      <div className="mb-12 text-center">
        <h2 className="text-2xl font-semibold text-ink sm:text-3xl">How Fantasy-AI Works</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm text-ink-tertiary">
          A real, end-to-end machine learning pipeline — not a black box.
        </p>
      </div>

      <div className="relative grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-5">
        <div
          className="absolute left-0 right-0 top-8 hidden h-px bg-gradient-to-r from-transparent via-border-medium to-transparent lg:block"
          aria-hidden="true"
        />
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: i * 0.08 }}
            className="relative flex flex-col items-center text-center lg:items-center"
          >
            <div className="z-10 flex h-16 w-16 items-center justify-center rounded-2xl border border-border-medium bg-surface-elevated text-gold shadow-card">
              <step.icon size={24} />
            </div>
            <h3 className="mt-4 text-sm font-semibold text-ink">{step.title}</h3>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-tertiary">{step.desc}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
