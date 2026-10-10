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
      "inline-flex items-center justify-center gap-2 rounded-xl font-black transition-all duration-150 disabled:bg-[#F8F7FA] disabled:text-[#B5B0BC] disabled:border-transparent disabled:shadow-none disabled:pointer-events-none active:translate-y-0.5 active:shadow-btn-pressed cursor-pointer";
    const variants: Record<string, string> = {
      primary:
        "bg-[#7041C5] text-white border border-[#5B32A8] shadow-btn-raised hover:bg-[#5B32A8] hover:shadow-glow-purple",
      secondary:
        "bg-white text-[#19171D] border-2 border-[#D8C7F4] shadow-btn-raised hover:bg-[#EEE7FA] hover:border-[#7041C5]",
      gold:
        "bg-[#B58A18] text-white border border-[#8C680E] shadow-btn-raised hover:bg-[#8C680E] hover:shadow-glow-mustard",
      mustard:
        "bg-[#B58A18] text-white border border-[#8C680E] shadow-btn-raised hover:bg-[#8C680E] hover:shadow-glow-mustard",
      ghost: "bg-transparent text-[#6F6A76] hover:text-[#19171D] hover:bg-[#F2EEF8] rounded-xl",
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
  tone?: "purple" | "mustard" | "baby" | "gold" | "signal" | "teal" | "coral" | "neutral";
  className?: string;
}

export function Badge({ children, tone = "neutral", className }: BadgeProps) {
  const tones: Record<string, string> = {
    purple: "bg-[#EEE7FA] text-[#452477] border-[#D8C7F4]",
    mustard: "bg-[#FDF8EC] text-[#8C680E] border-[#E5D08E]",
    baby: "bg-[#EDF6FC] text-[#246B9C] border-[#B9DDF5]",
    gold: "bg-[#FDF8EC] text-[#8C680E] border-[#E5D08E]",
    signal: "bg-[#EEE7FA] text-[#452477] border-[#D8C7F4]",
    teal: "bg-[#EDF6FC] text-[#246B9C] border-[#B9DDF5]",
    coral: "bg-[#FEF2F2] text-[#991B1B] border-red-200",
    neutral: "bg-[#F8F7FA] text-[#19171D] border-[#E8E3ED]",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-black leading-none shadow-sm",
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
        "rounded-chunky-lg border border-[#E8E3ED] bg-white text-[#19171D] shadow-card",
        interactive &&
          "transition-all duration-200 hover:border-[#7041C5] hover:shadow-card-hover cursor-pointer hover:-translate-y-0.5",
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
