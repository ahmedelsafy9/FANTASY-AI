import { forwardRef, type ButtonHTMLAttributes, type ReactNode, useState } from "react";
import { cn } from "@/lib/utils";

/* -------------------------------------------------------------------------- */
/* Button                                                                      */
/* -------------------------------------------------------------------------- */

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => {
    const base =
      "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all duration-200 disabled:opacity-40 disabled:pointer-events-none active:scale-[0.98]";
    const variants: Record<string, string> = {
      primary:
        "bg-gold text-void hover:bg-gold-bright shadow-glow hover:shadow-[0_0_48px_-6px_rgba(232,184,92,0.4)]",
      secondary:
        "bg-surface-elevated text-ink border border-border-medium hover:bg-surface-hover",
      ghost: "bg-transparent text-ink-secondary hover:text-ink hover:bg-surface",
    };
    const sizes: Record<string, string> = {
      sm: "text-sm px-3 py-1.5",
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
  tone?: "gold" | "signal" | "teal" | "coral" | "neutral";
  className?: string;
}

export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  const tones: Record<string, string> = {
    gold: "bg-gold/10 text-gold border-gold/25",
    signal: "bg-signal/10 text-signal-bright border-signal/25",
    teal: "bg-teal/10 text-teal border-teal/25",
    coral: "bg-coral/10 text-coral border-coral/25",
    neutral: "bg-white/5 text-ink-secondary border-border-medium",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium leading-none",
        tones[tone],
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
}

export function Card({ children, className, interactive, as = "div" }: CardProps) {
  const Comp = as;
  return (
    <Comp
      className={cn(
        "rounded-2xl border border-border-soft bg-surface shadow-card",
        interactive &&
          "transition-all duration-200 hover:border-border-medium hover:bg-surface-hover cursor-pointer",
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
      className={cn("animate-pulse-soft rounded-md bg-white/[0.06]", className)}
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
          className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border-medium bg-surface-elevated px-2.5 py-1.5 text-xs text-ink shadow-card"
        >
          {label}
        </span>
      )}
    </span>
  );
}
