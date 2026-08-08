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
        "relative overflow-hidden rounded-chunky-xl border-4 border-pitch-dark pitch-surface shadow-card-hover",
        className,
      )}
    >
      {/* Pitch markings */}
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        {/* Border */}
        <div className="absolute inset-4 rounded-chunky-lg border-2 border-white/35" />
        {/* Halfway line */}
        <div className="absolute left-4 right-4 top-1/2 h-0.5 bg-white/35" />
        {/* Center circle */}
        <div className="absolute left-1/2 top-1/2 h-24 w-24 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white/35 sm:h-28 sm:w-28" />
        {/* Center dot */}
        <div className="absolute left-1/2 top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-white/45" />
        {/* Top penalty area */}
        <div className="absolute left-1/2 top-4 h-[18%] w-[42%] -translate-x-1/2 border-b-2 border-l-2 border-r-2 border-white/30 sm:w-[36%]" />
        {/* Bottom penalty area */}
        <div className="absolute bottom-4 left-1/2 h-[18%] w-[42%] -translate-x-1/2 border-l-2 border-r-2 border-t-2 border-white/30 sm:w-[36%]" />
        <div className="absolute inset-0 bg-gradient-to-b from-white/10 via-transparent to-black/20" />
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

export function PitchRow({ children, className }: PitchRowProps) {
  return (
    <div className={cn("flex items-center justify-center gap-4 sm:gap-8", className)}>
      {children}
    </div>
  );
}
