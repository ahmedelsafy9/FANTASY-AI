import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PitchProps {
  children?: ReactNode;
  className?: string;
}

export function Pitch({ children, className }: PitchProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border-4 border-[#0F5124] pitch-surface shadow-2xl transition-all",
        className,
      )}
    >
      {/* SVG Pitch Markings Overlay */}
      <svg
        className="absolute inset-0 h-full w-full pointer-events-none opacity-80"
        viewBox="0 0 400 600"
        preserveAspectRatio="none"
        aria-hidden="true"
      >
        {/* Outer Boundary Line */}
        <rect
          x="16"
          y="16"
          width="368"
          height="568"
          rx="6"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2.5"
        />

        {/* Halfway Line */}
        <line
          x1="16"
          y1="300"
          x2="384"
          y2="300"
          stroke="#FFFFFF"
          strokeWidth="2"
        />

        {/* Centre Circle */}
        <circle
          cx="200"
          cy="300"
          r="48"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
        />
        {/* Centre Spot */}
        <circle cx="200" cy="300" r="3.5" fill="#FFFFFF" />

        {/* Top Goal Area & Penalty Box */}
        <rect
          x="100"
          y="16"
          width="200"
          height="95"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
        />
        <rect
          x="145"
          y="16"
          width="110"
          height="35"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
        />
        <circle cx="200" cy="78" r="3" fill="#FFFFFF" />
        <path
          d="M 160 111 A 45 45 0 0 0 240 111"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
        />

        {/* Bottom Goal Area & Penalty Box */}
        <rect
          x="100"
          y="489"
          width="200"
          height="95"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
        />
        <rect
          x="145"
          y="549"
          width="110"
          height="35"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
        />
        <circle cx="200" cy="522" r="3" fill="#FFFFFF" />
        <path
          d="M 160 489 A 45 45 0 0 1 240 489"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
        />

        {/* Corner Arcs */}
        <path d="M 16 32 A 16 16 0 0 0 32 16" fill="none" stroke="#FFFFFF" strokeWidth="2" />
        <path d="M 368 16 A 16 16 0 0 0 384 32" fill="none" stroke="#FFFFFF" strokeWidth="2" />
        <path d="M 16 568 A 16 16 0 0 1 32 584" fill="none" stroke="#FFFFFF" strokeWidth="2" />
        <path d="M 368 584 A 16 16 0 0 1 384 568" fill="none" stroke="#FFFFFF" strokeWidth="2" />
      </svg>

      {/* Subtle Vignette Gradient for Depth */}
      <div className="absolute inset-0 bg-gradient-to-b from-black/15 via-transparent to-black/25 pointer-events-none" />

      {/* Formation Content */}
      <div className="relative z-10 flex flex-col justify-between py-6 px-2 sm:px-6 min-h-[500px] sm:min-h-[580px]">
        {children}
      </div>
    </div>
  );
}

interface PitchRowProps {
  children: ReactNode;
  className?: string;
}

export function PitchRow({ children, className }: PitchRowProps) {
  return (
    <div className={cn("flex items-center justify-center gap-4 sm:gap-8", className)}>
      {children}
    </div>
  );
}
