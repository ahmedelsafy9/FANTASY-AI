import { useState, useRef, useEffect } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface TooltipProps {
  content: string;
  children: ReactNode;
  className?: string;
}

/**
 * Lightweight tooltip for explaining FPL concepts.
 * Hover on desktop, tap on mobile. Accessible via aria-label.
 */
export function Tooltip({ content, children, className }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!visible) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setVisible(false);
      }
    }
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, [visible]);

  return (
    <div
      ref={ref}
      className={cn("relative inline-flex", className)}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
      onClick={() => setVisible((v) => !v)}
    >
      {children}
      {visible && (
        <div
          role="tooltip"
          className="absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-normal rounded-xl border border-[#E2E8F0] bg-white px-3 py-2 text-xs font-medium text-[#475569] shadow-card max-w-[240px] leading-relaxed pointer-events-none animate-fade-up"
        >
          {content}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px">
            <div className="h-2 w-2 rotate-45 border-b border-r border-[#E2E8F0] bg-white" />
          </div>
        </div>
      )}
    </div>
  );
}
