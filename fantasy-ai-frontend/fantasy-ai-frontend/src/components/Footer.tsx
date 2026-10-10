import { Link } from "react-router-dom";
import { Zap } from "lucide-react";

const LINKS = [
  { label: "Overview", to: "/" },
  { label: "Squad Builder", to: "/squad" },
  { label: "Player Analytics", to: "/players" },
  { label: "Match Predictions", to: "/match-predictions" },
  { label: "Captain Hub", to: "/captain" },
];

export function Footer() {
  return (
    <footer className="border-t border-[#E8E3ED] bg-white pb-20 md:pb-0">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-6 px-4 py-8 sm:flex-row sm:justify-between lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#452477] text-[#B9DDF5] shadow-sm">
            <Zap size={15} />
          </div>
          <span className="font-display text-sm font-black text-[#19171D]">
            Fantasy<span className="text-[#7041C5]">.AI</span>
          </span>
          <span className="rounded-full bg-[#EEE7FA] px-2 py-0.5 text-[9px] font-black uppercase text-[#452477]">
            EPL Edition
          </span>
        </div>

        {/* Nav */}
        <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
          {LINKS.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className="text-xs font-bold text-[#6F6A76] transition-colors hover:text-[#7041C5]"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Copyright */}
        <p className="text-xs font-bold text-[#6F6A76]">
          &copy; {new Date().getFullYear()} FANTASY-AI Analytics
        </p>
      </div>
    </footer>
  );
}
