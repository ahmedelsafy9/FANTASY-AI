import { Link } from "react-router-dom";
import { WizardBrandMark } from "@/components/brand/WizardBrandMark";

const LINKS = [
  { label: "Overview", to: "/" },
  { label: "Player Analytics", to: "/players" },
  { label: "Match Predictions", to: "/match-predictions" },
  { label: "Squad Builder", to: "/squad" },
  { label: "Captain Hub", to: "/captain" },
  { label: "AI Assistant", to: "/assistant" },
];

export function Footer() {
  return (
    <footer className="border-t border-border bg-ivory-surface pb-20 md:pb-0">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 px-4 py-8 sm:flex-row sm:justify-between lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <WizardBrandMark size="sm" showWordmark={true} />
          <span className="rounded-full bg-gold-light border border-gold-border px-2 py-0.5 text-[9px] font-black uppercase text-gold-dark">
            Premier League Intelligence
          </span>
        </div>

        {/* Navigation Links */}
        <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
          {LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="text-xs font-bold text-ink-secondary transition-colors hover:text-gold-dark"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Copyright */}
        <p className="text-xs font-bold text-ink-secondary">
          &copy; {new Date().getFullYear()} Fantasy Wizard. Tactical FPL Analytics.
        </p>
      </div>
    </footer>
  );
}
