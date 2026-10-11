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
        "relative overflow-hidden rounded-3xl border-4 border-stadium-forest/70 pitch-surface shadow-2xl transition-all",
        className,
      )}
    >
      {/* SVG Pitch Markings Overlay */}
      <svg
        className="absolute inset-0 h-full w-full pointer-events-none opacity-75"
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
          rx="8"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2.5"
          strokeOpacity="0.85"
        />

        {/* Halfway Line */}
        <line
          x1="16"
          y1="300"
          x2="384"
          y2="300"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeOpacity="0.8"
        />

        {/* Centre Circle */}
        <circle
          cx="200"
          cy="300"
          r="48"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeOpacity="0.8"
        />
        {/* Centre Spot with Subtle Metallic Gold Core */}
        <circle cx="200" cy="300" r="4" fill="#C5A15B" stroke="#FFFFFF" strokeWidth="1" />

        {/* Top Goal Area & Penalty Box */}
        <rect
          x="100"
          y="16"
          width="200"
          height="95"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeOpacity="0.8"
        />
        <rect
          x="145"
          y="16"
          width="110"
          height="35"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeOpacity="0.8"
        />
        <circle cx="200" cy="78" r="3" fill="#FFFFFF" />
        <path
          d="M 160 111 A 45 45 0 0 0 240 111"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeOpacity="0.8"
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
          strokeOpacity="0.8"
        />
        <rect
          x="145"
          y="549"
          width="110"
          height="35"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeOpacity="0.8"
        />
        <circle cx="200" cy="522" r="3" fill="#FFFFFF" />
        <path
          d="M 160 489 A 45 45 0 0 1 240 489"
          fill="none"
          stroke="#FFFFFF"
          strokeWidth="2"
          strokeOpacity="0.8"
        />

        {/* Corner Arcs */}
        <path d="M 16 32 A 16 16 0 0 0 32 16" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeOpacity="0.8" />
        <path d="M 368 16 A 16 16 0 0 0 384 32" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeOpacity="0.8" />
        <path d="M 16 568 A 16 16 0 0 1 32 584" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeOpacity="0.8" />
        <path d="M 368 584 A 16 16 0 0 1 384 568" fill="none" stroke="#FFFFFF" strokeWidth="2" strokeOpacity="0.8" />
      </svg>

      {/* Stadium Night Match Floodlight Radial Overlay */}
      <div className="absolute inset-0 bg-radial from-gold-metallic/10 via-transparent to-stadium-dark/40 pointer-events-none" />

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
