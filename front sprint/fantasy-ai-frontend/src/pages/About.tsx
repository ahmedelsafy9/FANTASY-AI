import { AlertCircle, Database, Github } from "lucide-react";
import { HowItWorks } from "@/sections/HowItWorks";
import { Badge } from "@/components/ui/primitives";

const TECH = [
  "Python", "pandas", "scikit-learn", "XGBoost", "LightGBM",
  "FastAPI", "React", "TypeScript", "Vite", "Tailwind CSS", "Framer Motion", "Recharts",
];

export default function About() {
  return (
    <div className="mx-auto max-w-3xl px-5 py-14 pb-24 lg:px-8">
      <h1 className="text-3xl font-semibold text-ink sm:text-4xl">About Fantasy-AI</h1>
      <p className="mt-4 text-lg leading-relaxed text-ink-secondary">
        Fantasy-AI is an end-to-end machine learning system that predicts
        Fantasy Premier League player points, built as a real software
        project — historical data ingestion, validation, feature
        engineering, model training and comparison, a prediction pipeline,
        and this interface, all wired together and honest about what it
        can and can't yet do.
      </p>

      <HowItWorks />

      <section id="technology" className="mt-4">
        <h2 className="text-xl font-semibold text-ink">Technology</h2>
        <div className="mt-4 flex flex-wrap gap-2">
          {TECH.map((t) => (
            <Badge key={t} tone="neutral">
              {t}
            </Badge>
          ))}
        </div>
      </section>

      <section className="mt-12 rounded-2xl border border-signal/25 bg-signal/[0.05] p-6">
        <div className="flex items-start gap-3">
          <AlertCircle size={20} className="mt-0.5 shrink-0 text-signal" />
          <div>
            <h2 className="text-base font-semibold text-ink">
              Known limitation: next-Gameweek prediction
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
              Fantasy-AI's model is trained on completed matches. To predict
              an upcoming, unplayed Gameweek, the backend currently uses
              each player's <em>most recently played</em> match as a proxy
              for their next one — it does not yet know the actual upcoming
              opponent, home/away status for that specific fixture, or
              official injury/availability news. This is a deliberate,
              documented simplification of the current backend, not a bug
              in this interface — we chose to surface real (if imperfect)
              predictions rather than hide the model or fabricate
              fixture-aware data it doesn't have.
            </p>
            <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
              This UI is built to consume improved, fixture-aware
              predictions the moment the backend supports them, without
              requiring a redesign.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-8 rounded-2xl border border-border-soft bg-surface p-6">
        <div className="flex items-start gap-3">
          <Database size={20} className="mt-0.5 shrink-0 text-ink-tertiary" />
          <div>
            <h2 className="text-base font-semibold text-ink">Data honesty</h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-secondary">
              Every number in this app comes from the live backend API. No
              player, prediction, fixture, or statistic is hardcoded. Where
              a field isn't available from the backend — a player photo,
              team crest, fixture difficulty rating, or explicit confidence
              score — this interface shows "N/A" or an honest empty state
              rather than inventing one.
            </p>
          </div>
        </div>
      </section>

      <section className="mt-8 flex items-center justify-between rounded-2xl border border-border-soft bg-surface p-6">
        <div>
          <h2 className="text-base font-semibold text-ink">Source</h2>
          <p className="mt-1 text-sm text-ink-tertiary">Version 0.1.0</p>
        </div>
        <a
          href="https://github.com"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-2 rounded-lg border border-border-medium px-4 py-2 text-sm text-ink-secondary transition-colors hover:text-ink"
        >
          <Github size={16} /> GitHub
        </a>
      </section>
    </div>
  );
}
