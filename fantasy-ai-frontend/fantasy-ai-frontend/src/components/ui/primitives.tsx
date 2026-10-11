import { forwardRef, type ButtonHTMLAttributes, type ReactNode, useState } from "react";
import { cn } from "@/lib/utils";

/* -------------------------------------------------------------------------- */
/* Button                                                                      */
/* -------------------------------------------------------------------------- */

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "gold" | "ghost" | "mustard";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => {
    const base =
      "inline-flex items-center justify-center gap-2 rounded-xl font-black transition-all duration-150 disabled:bg-ivory-subtle disabled:text-ink-disabled disabled:border-transparent disabled:shadow-none disabled:pointer-events-none active:translate-y-0.5 active:shadow-btn-pressed cursor-pointer select-none";
    const variants: Record<string, string> = {
      primary:
        "bg-stadium-deep text-ivory-surface border border-stadium-forest shadow-btn-raised hover:bg-stadium-forest hover:border-gold-metallic/60",
      secondary:
        "bg-ivory-surface text-ink-primary border border-border shadow-btn-raised hover:bg-ivory-subtle hover:border-gold-metallic/50",
      gold:
        "bg-gold-metallic text-stadium-dark border border-gold-border shadow-glow-gold hover:bg-gold-bright hover:shadow-glow-gold",
      mustard:
        "bg-gold-metallic text-stadium-dark border border-gold-border shadow-glow-gold hover:bg-gold-bright hover:shadow-glow-gold",
      ghost:
        "bg-transparent text-ink-secondary hover:text-ink-primary hover:bg-ivory-subtle rounded-xl",
    };
    const sizes: Record<string, string> = {
      sm: "text-xs px-3.5 py-2",
      md: "text-sm px-5 py-2.5",
      lg: "text-base px-7 py-3.5",
    };
    return (
      <button
        ref={ref}
        className={cn(base, variants[variant], sizes[size], className)}
        {...props}
      >
        {children}
      </button>
    );
  },
);
Button.displayName = "Button";

/* -------------------------------------------------------------------------- */
/* Badge                                                                       */
/* -------------------------------------------------------------------------- */

interface BadgeProps {
  children: ReactNode;
  tone?: "gold" | "stadium" | "pitch" | "purple" | "mustard" | "baby" | "signal" | "teal" | "coral" | "neutral";
  className?: string;
}

export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  const tones: Record<string, string> = {
    gold: "bg-gold-light text-gold-dark border-gold-border",
    mustard: "bg-gold-light text-gold-dark border-gold-border",
    stadium: "bg-stadium-deep text-ivory-surface border-stadium-forest",
    pitch: "bg-stadium-deep text-ivory-surface border-stadium-forest",
    purple: "bg-stadium-surface/10 text-stadium-deep border-stadium-forest/30",
    baby: "bg-[#EEF5F9] text-[#1E5A84] border-[#BDD7E7]",
    signal: "bg-stadium-deep text-gold-bright border-gold-border",
    teal: "bg-emerald-50 text-emerald-800 border-emerald-200",
    coral: "bg-rose-50 text-rose-800 border-rose-200",
    neutral: "bg-ivory-subtle text-ink-primary border-border",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-black leading-none shadow-xs select-none",
        tones[tone] || tones.neutral,
        className,
      )}
    >
      {children}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Card                                                                        */
/* -------------------------------------------------------------------------- */

interface CardProps {
  children: ReactNode;
  className?: string;
  interactive?: boolean;
  as?: "div" | "article";
  onClick?: () => void;
}

export function Card({ children, className, interactive, as = "div", onClick }: CardProps) {
  const Comp = as;
  return (
    <Comp
      onClick={onClick}
      className={cn(
        "rounded-chunky-lg border border-border bg-ivory-surface text-ink-primary shadow-card",
        interactive &&
          "transition-all duration-200 hover:border-gold-border hover:shadow-card-hover cursor-pointer hover:-translate-y-0.5",
        className,
      )}
    >
      {children}
    </Comp>
  );
}

/* -------------------------------------------------------------------------- */
/* Skeleton                                                                    */
/* -------------------------------------------------------------------------- */

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn("animate-pulse-soft rounded-xl bg-[#E6E0D4]", className)}
      aria-hidden="true"
    />
  );
}

/* -------------------------------------------------------------------------- */
/* Tooltip                                                                     */
/* -------------------------------------------------------------------------- */

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
    >
      {children}
      {open && (
        <span
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded-xl border border-gold-border/60 bg-stadium-dark px-3 py-1.5 text-xs font-extrabold text-ivory-surface shadow-card pointer-events-none"
        >
          {label}
        </span>
      )}
    </span>
  );
}
