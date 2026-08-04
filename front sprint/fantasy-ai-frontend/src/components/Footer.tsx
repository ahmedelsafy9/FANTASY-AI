import { Github, Zap } from "lucide-react";

export function Footer() {
  return (
    <footer className="border-t border-border-soft bg-void-soft">
      <div className="mx-auto max-w-7xl px-5 py-12 lg:px-8">
        <div className="flex flex-col gap-8 md:flex-row md:justify-between">
          <div className="max-w-sm">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gold/10 text-gold">
                <Zap size={15} strokeWidth={2.5} />
              </div>
              <span className="font-display text-base font-semibold text-ink">
                Fantasy<span className="text-gold">-AI</span>
              </span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-ink-tertiary">
              AI-powered Fantasy Premier League analytics — built on real
              historical data, trained models, and an honest, transparent
              prediction pipeline.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-8 sm:grid-cols-3">
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-tertiary">
                Product
              </h4>
              <ul className="mt-3 flex flex-col gap-2 text-sm text-ink-secondary">
                <li><a href="/dashboard" className="hover:text-ink">Dashboard</a></li>
                <li><a href="/predictions" className="hover:text-ink">Predictions</a></li>
                <li><a href="/players" className="hover:text-ink">Players</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-tertiary">
                Fantasy-AI
              </h4>
              <ul className="mt-3 flex flex-col gap-2 text-sm text-ink-secondary">
                <li><a href="/about" className="hover:text-ink">About</a></li>
                <li><a href="/about#technology" className="hover:text-ink">Technology</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wide text-ink-tertiary">
                Project
              </h4>
              <ul className="mt-3 flex flex-col gap-2 text-sm text-ink-secondary">
                <li>
                  <a
                    href="https://github.com"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 hover:text-ink"
                  >
                    <Github size={14} /> GitHub
                  </a>
                </li>
                <li className="numeral text-ink-tertiary">v0.1.0</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="mt-10 border-t border-border-soft pt-6 text-xs text-ink-tertiary">
          Fantasy-AI is an independent analytics project and is not affiliated
          with the Premier League or Fantasy Premier League.
        </div>
      </div>
    </footer>
  );
}
