import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PitchProps {
  children?: ReactNode;
  className?: string;
}

/**
 * A visual football pitch component for the squad builder.
 * Renders a green pitch background with subtle markings (center circle,
 * halfway line, penalty areas). Children (PlayerTokens) should be
 * positioned using the PitchRow component for formation layout.
 */
export function Pitch({ children, className }: PitchProps) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-2xl border border-emerald-dim/40 pitch-surface",
        className,
      )}
    >
      {/* Pitch markings */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        {/* Border */}
        <div className="absolute inset-3 rounded-xl border border-white/[0.08]" />
        {/* Halfway line */}
        <div className="absolute left-3 right-3 top-1/2 h-px bg-white/[0.08]" />
        {/* Center circle */}
        <div className="absolute left-1/2 top-1/2 h-20 w-20 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/[0.08] sm:h-24 sm:w-24" />
        {/* Center dot */}
        <div className="absolute left-1/2 top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/10" />
        {/* Top penalty area */}
        <div className="absolute left-1/2 top-3 h-[18%] w-[40%] -translate-x-1/2 border-b border-l border-r border-white/[0.06] sm:w-[35%]" />
        {/* Bottom penalty area */}
        <div className="absolute bottom-3 left-1/2 h-[18%] w-[40%] -translate-x-1/2 border-l border-r border-t border-white/[0.06] sm:w-[35%]" />
        {/* Subtle gradient overlay for depth */}
        <div className="absolute inset-0 bg-gradient-to-b from-white/[0.02] via-transparent to-black/10" />
      </div>

      {/* Formation content */}
      <div className="relative z-10 flex flex-col gap-4 px-4 py-6 sm:gap-6 sm:px-8 sm:py-8">
        {children}
      </div>
    </div>
  );
}

interface PitchRowProps {
  children: ReactNode;
  className?: string;
}

/** A horizontal row in the pitch formation, centering its children (PlayerTokens). */
export function PitchRow({ children, className }: PitchRowProps) {
  return (
    <div className={cn("flex items-center justify-center gap-4 sm:gap-8", className)}>
      {children}
    </div>
  );
}
