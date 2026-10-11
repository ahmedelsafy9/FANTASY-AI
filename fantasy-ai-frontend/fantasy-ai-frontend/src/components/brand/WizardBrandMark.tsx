import { cn } from "@/lib/utils";

interface WizardBrandMarkProps {
  className?: string;
  size?: "sm" | "md" | "lg" | "xl";
  showWordmark?: boolean;
  wordmarkClassName?: string;
  darkSurface?: boolean;
}

const SIZE_MAP = {
  sm: { icon: "h-7 w-7", text: "text-base" },
  md: { icon: "h-9 w-9", text: "text-lg" },
  lg: { icon: "h-12 w-12", text: "text-2xl" },
  xl: { icon: "h-16 w-16", text: "text-3xl" },
};

export function WizardBrandMark({
  className,
  size = "md",
  showWordmark = true,
  wordmarkClassName,
  darkSurface = false,
}: WizardBrandMarkProps) {
  const dims = SIZE_MAP[size];

  return (
    <div className={cn("inline-flex items-center gap-2.5 select-none", className)}>
      {/* Visual Mark */}
      <svg
        className={cn("shrink-0 drop-shadow-sm", dims.icon)}
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <defs>
          <linearGradient id="crestPitch" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#10291F" />
            <stop offset="100%" stopColor="#091B15" />
          </linearGradient>
          <linearGradient id="crestGold" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#E2C98A" />
            <stop offset="50%" stopColor="#C5A15B" />
            <stop offset="100%" stopColor="#9D7A3C" />
          </linearGradient>
        </defs>

        {/* Outer Shield / Stadium Badge */}
        <rect
          width="48"
          height="48"
          rx="12"
          fill="url(#crestPitch)"
        />
        <rect
          x="1"
          y="1"
          width="46"
          height="46"
          rx="11"
          stroke="url(#crestGold)"
          strokeWidth="1.5"
          strokeOpacity="0.75"
        />

        {/* Subtle Tactical Orbit */}
        <circle
          cx="24"
          cy="24"
          r="14"
          stroke="url(#crestGold)"
          strokeWidth="1"
          strokeDasharray="2 3"
          strokeOpacity="0.6"
        />

        {/* Wizard Strategic Star combined with Football Geometry */}
        <path
          d="M24 13L26.5 21.5L35 24L26.5 26.5L24 35L21.5 26.5L13 24L21.5 21.5Z"
          fill="url(#crestGold)"
        />
        {/* Core Tactical Hub */}
        <circle
          cx="24"
          cy="24"
          r="3.5"
          fill="#091B15"
          stroke="url(#crestGold)"
          strokeWidth="1.2"
        />
        <circle cx="24" cy="24" r="1.3" fill="#E2C98A" />

        {/* Corner Precision Nodes */}
        <circle cx="24" cy="9.5" r="1.2" fill="#C5A15B" />
        <circle cx="38.5" cy="24" r="1.2" fill="#C5A15B" />
        <circle cx="24" cy="38.5" r="1.2" fill="#C5A15B" />
        <circle cx="9.5" cy="24" r="1.2" fill="#C5A15B" />
      </svg>

      {/* Wordmark */}
      {showWordmark && (
        <div className="flex flex-col leading-none">
          <div className="flex items-baseline gap-1">
            <span
              className={cn(
                "font-display font-black tracking-tight",
                dims.text,
                darkSurface ? "text-ivory-surface" : "text-ink-primary",
                wordmarkClassName,
              )}
            >
              FANTASY
            </span>
            <span
              className={cn(
                "font-display font-black tracking-tight text-gradient-gold",
                dims.text,
              )}
            >
              WIZARD
            </span>
          </div>
          <span
            className={cn(
              "text-[9px] font-black uppercase tracking-widest mt-0.5",
              darkSurface ? "text-stadium-lines opacity-70" : "text-ink-secondary",
            )}
          >
            Tactical Intelligence
          </span>
        </div>
      )}
    </div>
  );
}
