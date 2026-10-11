import { cn } from "@/lib/utils";

interface AssistantIconProps {
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  glow?: boolean;
}

const SIZE_MAP = {
  sm: "h-6 w-6",
  md: "h-8 w-8",
  lg: "h-12 w-12",
  xl: "h-16 w-16",
};

export function AssistantIcon({
  className,
  size = "md",
  glow = false,
}: AssistantIconProps) {
  return (
    <div
      className={cn(
        "relative inline-flex items-center justify-center shrink-0",
        glow && "after:absolute after:inset-0 after:rounded-xl after:bg-[#C5A15B]/20 after:blur-md",
        className,
      )}
    >
      <svg
        className={cn("drop-shadow-sm transition-transform", SIZE_MAP[size])}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="aiPitchGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#1B4031" />
            <stop offset="100%" stopColor="#091B15" />
          </linearGradient>
          <linearGradient id="aiGoldGrad" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#E2C98A" />
            <stop offset="60%" stopColor="#C5A15B" />
            <stop offset="100%" stopColor="#9D7A3C" />
          </linearGradient>
        </defs>

        {/* Tactical Hexagonal Shield */}
        <path
          d="M20 2L35 10.5V29.5L20 38L5 29.5V10.5L20 2Z"
          fill="url(#aiPitchGrad)"
          stroke="url(#aiGoldGrad)"
          strokeWidth="1.5"
        />

        {/* Tactical Coordinates Grid */}
        <line x1="20" y1="6" x2="20" y2="34" stroke="#C5A15B" strokeWidth="0.8" strokeOpacity="0.4" strokeDasharray="1.5 1.5" />
        <line x1="9" y1="20" x2="31" y2="20" stroke="#C5A15B" strokeWidth="0.8" strokeOpacity="0.4" strokeDasharray="1.5 1.5" />

        {/* Central Strategic Spark */}
        <path
          d="M20 11L22.2 17.8L29 20L22.2 22.2L20 29L17.8 22.2L11 20L17.8 17.8Z"
          fill="url(#aiGoldGrad)"
        />

        {/* Intelligence Core */}
        <circle cx="20" cy="20" r="2.8" fill="#091B15" stroke="#E2C98A" strokeWidth="1" />
        <circle cx="20" cy="20" r="1.1" fill="#FFFFFF" />

        {/* Corner Precision Dots */}
        <circle cx="20" cy="7" r="0.9" fill="#E2C98A" />
        <circle cx="31" cy="14" r="0.9" fill="#E2C98A" />
        <circle cx="31" cy="26" r="0.9" fill="#E2C98A" />
        <circle cx="20" cy="33" r="0.9" fill="#E2C98A" />
        <circle cx="9" cy="26" r="0.9" fill="#E2C98A" />
        <circle cx="9" cy="14" r="0.9" fill="#E2C98A" />
      </svg>
    </div>
  );
}
