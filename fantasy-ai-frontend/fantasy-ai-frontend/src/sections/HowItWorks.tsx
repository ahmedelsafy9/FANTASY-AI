import { motion } from "framer-motion";
import { Database, Cpu, LineChart, Sparkles, Trophy } from "lucide-react";

const STEPS = [
  { icon: Database, title: "Data Ingestion", desc: "Historical Premier League data ingested and validated.", color: "text-[#059669] bg-[#ECFDF5]" },
  { icon: LineChart, title: "Feature Engineering", desc: "Form, fixture context, and price trends computed.", color: "text-indigo-600 bg-indigo-100" },
  { icon: Cpu, title: "Machine Learning", desc: "Gradient boosting models trained and evaluated.", color: "text-teal-700 bg-teal-100" },
  { icon: Sparkles, title: "Predictions", desc: "Model projects expected points for upcoming gameweeks.", color: "text-[#92400E] bg-[#FFFBEB]" },
  { icon: Trophy, title: "Squad Edge", desc: "AI analytics inform your transfers, captaincy, and XI.", color: "text-[#92400E] bg-[#FFFBEB]" },
];

export function HowItWorks() {
  return (
    <section className="mx-auto max-w-6xl px-4 py-12 lg:px-8">
      <div className="mb-10 text-center">
        <h2 className="font-display text-2xl font-black text-[#0F172A] sm:text-3xl">How Fantasy-AI Works</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm font-semibold text-[#64748B]">
          An end-to-end machine learning pipeline powering FPL analytics.
        </p>
      </div>

      <div className="relative grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {STEPS.map((step, i) => (
          <motion.div
            key={step.title}
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.45, delay: i * 0.08 }}
            className="relative flex flex-col items-center text-center p-4 rounded-chunky-lg border border-[#E2E8F0] bg-white shadow-card"
          >
            <div className={`z-10 flex h-14 w-14 items-center justify-center rounded-2xl border border-[#E2E8F0] shadow-sm ${step.color}`}>
              <step.icon size={22} />
            </div>
            <h3 className="mt-3 text-sm font-black text-[#0F172A]">{step.title}</h3>
            <p className="mt-1 text-xs font-semibold leading-relaxed text-[#64748B]">{step.desc}</p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
