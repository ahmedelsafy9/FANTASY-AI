import { useState } from "react";
import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface AdvancedToggleProps {
  label?: string;
  children: ReactNode;
  className?: string;
  defaultOpen?: boolean;
}

/**
 * Progressive disclosure toggle for technical/advanced information.
 * Default view stays simple — power users can expand for details.
 */
export function AdvancedToggle({
  label = "More details",
  children,
  className,
  defaultOpen = false,
}: AdvancedToggleProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className={cn("flex flex-col", className)}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 text-xs font-bold text-[#64748B] hover:text-[#0F172A] transition-colors cursor-pointer py-1"
        aria-expanded={open}
      >
        <ChevronDown
          size={14}
          className={cn(
            "transition-transform duration-200",
            open && "rotate-180",
          )}
        />
        {label}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="overflow-hidden"
          >
            <div className="pt-3">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
