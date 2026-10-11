import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { AssistantIcon } from "@/components/brand/AssistantIcon";

export function AssistantQuickLauncher() {
  const location = useLocation();

  // Hide when already on the dedicated Assistant page
  if (location.pathname === "/assistant") return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, scale: 0.85, y: 10 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.85, y: 10 }}
        className="fixed bottom-5 right-5 z-40 hidden sm:block"
      >
        <Link
          to="/assistant"
          className="group flex items-center gap-2.5 rounded-full border border-gold-border/70 bg-stadium-deep px-4 py-2.5 text-ivory-surface shadow-card-hover transition-all duration-200 hover:scale-105 hover:bg-stadium-forest hover:shadow-glow-gold"
          aria-label="Open Fantasy Wizard AI Assistant"
          id="assistant-quick-launcher"
        >
          <AssistantIcon size="sm" glow={true} />
          <div className="flex flex-col text-left pr-1">
            <span className="font-display text-xs font-black tracking-tight text-ivory-surface group-hover:text-gold-bright transition-colors">
              Wizard AI
            </span>
            <span className="text-[10px] font-bold text-gold-muted leading-none">
              Tactical Co-Pilot
            </span>
          </div>
        </Link>
      </motion.div>
    </AnimatePresence>
  );
}
