import { forwardRef, type ButtonHTMLAttributes, type ReactNode, useState } from "react";
import { cn } from "@/lib/utils";

/* -------------------------------------------------------------------------- */
/* Button                                                                      */
/* -------------------------------------------------------------------------- */

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "gold" | "ghost";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", size = "md", children, ...props }, ref) => {
    const base =
      "inline-flex items-center justify-center gap-2 rounded-xl font-black transition-all duration-150 disabled:bg-[#F1F5F9] disabled:text-[#94A3B8] disabled:border-transparent disabled:shadow-none disabled:pointer-events-none active:translate-y-0.5 active:shadow-btn-pressed cursor-pointer";
    const variants: Record<string, string> = {
      primary:
        "bg-[#10B981] text-white border border-[#059669] shadow-btn-raised hover:bg-[#059669] hover:shadow-glow",
      secondary:
        "bg-white text-[#0F172A] border-2 border-[#10B981] shadow-btn-raised hover:bg-[#ECFDF5] hover:border-[#059669]",
      gold:
        "bg-[#F59E0B] text-[#0F172A] border border-[#D97706] shadow-btn-raised hover:bg-[#D97706] hover:text-white hover:shadow-glow-gold",
      ghost: "bg-transparent text-[#475569] hover:text-[#0F172A] hover:bg-[#F1F5F9] rounded-xl",
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
  tone?: "gold" | "signal" | "teal" | "coral" | "neutral";
  className?: string;
}

export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  const tones: Record<string, string> = {
    gold: "bg-[#FFFBEB] text-[#92400E] border-[#FDE68A]",
    signal: "bg-[#EEF2FF] text-[#3730A3] border-indigo-200",
    teal: "bg-[#ECFDF5] text-[#059669] border-[#A7F3D0]",
    coral: "bg-[#FEF2F2] text-[#991B1B] border-red-200",
    neutral: "bg-[#F1F5F9] text-[#334155] border-[#CBD5E1]",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-black leading-none shadow-sm",
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
        "rounded-chunky-lg border border-[#E2E8F0] bg-white text-[#0F172A] shadow-card",
        interactive &&
          "transition-all duration-200 hover:border-[#10B981] hover:shadow-card-playful cursor-pointer hover:-translate-y-0.5",
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
      className={cn("animate-pulse-soft rounded-xl bg-[#E2E8F0]", className)}
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
          className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded-xl border border-[#CBD5E1] bg-[#0F172A] px-3 py-1.5 text-xs font-extrabold text-white shadow-card"
        >
          {label}
        </span>
      )}
    </span>
  );
}
