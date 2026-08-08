import { AlertCircle, Database, Github } from "lucide-react";
import { HowItWorks } from "@/sections/HowItWorks";
import { Badge } from "@/components/ui/primitives";

const TECH = [
  "Python", "pandas", "scikit-learn", "XGBoost", "LightGBM",
  "FastAPI", "React", "TypeScript", "Vite", "Tailwind CSS", "Framer Motion", "Recharts",
];

export default function About() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-10 pb-24 lg:px-8">
      <h1 className="text-3xl font-black text-[#0F172A] sm:text-4xl">About Fantasy-AI</h1>
      <p className="mt-4 text-base font-semibold leading-relaxed text-[#475569]">
        Fantasy-AI is an end-to-end machine learning system that predicts
        Fantasy Premier League player points, built as a real software
        project — historical data ingestion, validation, feature
        engineering, model training and comparison, a prediction pipeline,
        and this interface.
      </p>

      <HowItWorks />

      <section id="technology" className="mt-8">
        <h2 className="text-xl font-black text-[#0F172A]">Technology Stack</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {TECH.map((t) => (
            <Badge key={t} tone="neutral">
              {t}
            </Badge>
          ))}
        </div>
      </section>

      <section className="mt-10 rounded-chunky-lg border border-indigo-200 bg-indigo-50 p-6 shadow-sm">
        <div className="flex items-start gap-3">
          <AlertCircle size={22} className="mt-0.5 shrink-0 text-indigo-600" />
          <div>
            <h2 className="text-base font-black text-[#0F172A]">
              Model Note: Gameweek Predictions
            </h2>
            <p className="mt-2 text-sm font-semibold leading-relaxed text-[#475569]">
              Fantasy-AI's model is trained on completed matches. To predict
              an upcoming, unplayed Gameweek, the backend currently uses
              each player's <em>most recently played</em> match as a proxy
              for their next one.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6 rounded-chunky-lg border border-[#E2E8F0] bg-white p-6 shadow-card">
        <div className="flex items-start gap-3">
          <Database size={22} className="mt-0.5 shrink-0 text-[#059669]" />
          <div>
            <h2 className="text-base font-black text-[#0F172A]">Data Honesty</h2>
            <p className="mt-2 text-sm font-semibold leading-relaxed text-[#475569]">
              Every number in this app comes directly from the live backend API. No
              player, prediction, fixture, or statistic is hardcoded.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-6 flex items-center justify-between rounded-chunky-lg border border-[#E2E8F0] bg-white p-6 shadow-card">
        <div>
          <h2 className="text-base font-black text-[#0F172A]">Source Code</h2>
          <p className="mt-1 text-xs font-bold text-[#94A3B8]">Version 0.1.0</p>
        </div>
        <a
          href="https://github.com"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 rounded-xl border-2 border-[#E2E8F0] bg-white px-4 py-2 text-sm font-extrabold text-[#0F172A] shadow-btn-raised transition-all hover:border-[#CBD5E1]"
        >
          <Github size={16} /> GitHub
        </a>
      </section>
    </div>
  );
}
