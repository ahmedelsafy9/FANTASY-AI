import { Link } from "react-router-dom";
import { Zap } from "lucide-react";

const LINKS = [
  { label: "Predictions", to: "/predictions" },
  { label: "Players", to: "/players" },
  { label: "Squad Builder", to: "/squad" },
  { label: "Captain Pick", to: "/captain" },
  { label: "About", to: "/about" },
];

export function Footer() {
  return (
    <footer className="border-t border-emerald/10 bg-void pb-20 md:pb-0">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 px-5 py-10 sm:flex-row sm:justify-between lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald/10 text-emerald">
            <Zap size={13} />
          </div>
          <span className="font-display text-sm font-bold text-ink-secondary">
            Fantasy<span className="text-emerald">-AI</span>
          </span>
        </div>

        {/* Nav */}
        <nav className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1">
          {LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="text-xs text-ink-tertiary transition-colors hover:text-ink-secondary"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Copyright */}
        <p className="text-xs text-ink-tertiary">
          &copy; {new Date().getFullYear()} Fantasy-AI
        </p>
      </div>
    </footer>
  );
}
