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
    <footer className="border-t border-[#E2E8F0] bg-white pb-20 md:pb-0">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 px-4 py-8 sm:flex-row sm:justify-between lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-2">
          <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[#10B981] text-white shadow-sm">
            <Zap size={14} />
          </div>
          <span className="font-display text-sm font-black text-[#0F172A]">
            Fantasy<span className="text-[#10B981]">.AI</span>
          </span>
        </div>

        {/* Nav */}
        <nav className="flex flex-wrap items-center justify-center gap-x-5 gap-y-1">
          {LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="text-xs font-bold text-[#64748B] transition-colors hover:text-[#0F172A]"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Copyright */}
        <p className="text-xs font-bold text-[#94A3B8]">
          &copy; {new Date().getFullYear()} Fantasy-AI
        </p>
      </div>
    </footer>
  );
}
