import { useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Menu,
  X,
  Zap,
  BarChart3,
  Users,
  Shield,
  Crown,
  Home,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";

type LucideIcon = typeof Home;

interface NavLinkItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

interface SecondaryLinkItem {
  to: string;
  label: string;
}

const NAV_LINKS: NavLinkItem[] = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/predictions", label: "Predictions", icon: BarChart3 },
  { to: "/players", label: "Players", icon: Users },
  { to: "/squad", label: "Squad", icon: Shield },
  { to: "/captain", label: "Captain", icon: Crown },
];

const SECONDARY_LINKS: SecondaryLinkItem[] = [
  { to: "/about", label: "About" },
];

export function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const { user, logout, openLoginModal } = useAuth();

  return (
    <>
      {/* Desktop top navigation */}
      <header className="sticky top-0 z-40 border-b border-border-soft bg-void/85 backdrop-blur-xl">
        <nav className="mx-auto flex h-14 max-w-7xl items-center justify-between px-5 lg:px-8">
          <NavLink to="/" className="flex items-center gap-2.5" aria-label="Fantasy-AI home">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald/10 text-emerald">
              <Zap size={16} strokeWidth={2.5} />
            </div>
            <span className="font-display text-base font-bold tracking-tight text-ink">
              Fantasy<span className="text-emerald">-AI</span>
            </span>
          </NavLink>

          {/* Desktop links */}
          <ul className="hidden items-center gap-0.5 md:flex">
            {NAV_LINKS.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  end={link.end}
                  className={({ isActive }) =>
                    cn(
                      "relative flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                      isActive ? "text-ink" : "text-ink-secondary hover:text-ink",
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {(() => { const Icon = link.icon; return <Icon size={14} className={isActive ? "text-emerald" : "opacity-50"} />; })()}
                      {link.label}
                      {isActive && (
                        <motion.span
                          layoutId="nav-active"
                          className="absolute inset-x-2 -bottom-[9px] h-[2px] rounded-full bg-emerald"
                          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                        />
                      )}
                    </>
                  )}
                </NavLink>
              </li>
            ))}
            {SECONDARY_LINKS.map((link) => (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  className={({ isActive }) =>
                    cn(
                      "relative rounded-lg px-3 py-1.5 text-sm font-medium transition-colors",
                      isActive ? "text-ink" : "text-ink-tertiary hover:text-ink-secondary",
                    )
                  }
                >
                  {link.label}
                </NavLink>
              </li>
            ))}
          </ul>

          {/* Desktop Right Auth Widget */}
          <div className="hidden items-center gap-3 md:flex">
            {user ? (
              <div className="flex items-center gap-2.5 rounded-full border border-border-medium bg-surface px-3 py-1 shadow-sm">
                <img
                  src={user.picture}
                  alt={user.name}
                  className="h-6 w-6 rounded-full object-cover ring-2 ring-emerald/40"
                />
                <span className="text-xs font-semibold leading-tight text-ink">
                  {user.name}
                </span>
                <button
                  onClick={logout}
                  title="Sign out"
                  aria-label="Sign out"
                  className="ml-1 rounded-full p-1 text-ink-tertiary transition-colors hover:bg-coral/10 hover:text-coral"
                >
                  <LogOut size={14} />
                </button>
              </div>
            ) : (
              <button
                onClick={openLoginModal}
                className="rounded-full bg-emerald px-4 py-1.5 text-xs font-semibold text-void transition-opacity hover:opacity-90 shadow-sm"
              >
                Sign In with Gmail
              </button>
            )}
          </div>

          {/* Mobile hamburger */}
          <button
            className="rounded-lg p-2 text-ink md:hidden"
            onClick={() => setMobileOpen((o) => !o)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </nav>

        {/* Mobile slide-down menu */}
        <AnimatePresence>
          {mobileOpen && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: "auto", opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              className="overflow-hidden border-t border-border-soft bg-void md:hidden"
            >
              <ul className="flex flex-col gap-1 px-5 py-4">
                {([...NAV_LINKS, ...SECONDARY_LINKS] as (NavLinkItem | SecondaryLinkItem)[]).map((link) => {
                  const Icon = "icon" in link ? (link as NavLinkItem).icon : null;
                  return (
                    <li key={link.to}>
                      <NavLink
                        to={link.to}
                        end={"end" in link ? (link as NavLinkItem).end : undefined}
                        onClick={() => setMobileOpen(false)}
                        className={({ isActive }) =>
                          cn(
                            "flex items-center gap-3 rounded-lg px-3 py-2.5 text-base font-medium transition-colors",
                            isActive
                              ? "bg-emerald/10 text-emerald"
                              : "text-ink-secondary hover:bg-surface hover:text-ink",
                          )
                        }
                      >
                        {Icon && <Icon size={18} />}
                        {link.label}
                      </NavLink>
                    </li>
                  );
                })}
                <li className="pt-2 border-t border-border-soft">
                  {user ? (
                    <div className="flex items-center justify-between py-2">
                      <div className="flex items-center gap-2">
                        <img src={user.picture} alt={user.name} className="h-8 w-8 rounded-full object-cover" />
                        <div className="flex flex-col">
                          <span className="text-sm font-semibold text-ink">{user.name}</span>
                          <span className="text-xs text-ink-tertiary">{user.email}</span>
                        </div>
                      </div>
                      <button
                        onClick={() => { logout(); setMobileOpen(false); }}
                        className="rounded-lg p-2 text-coral hover:bg-coral/10"
                      >
                        <LogOut size={18} />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => { openLoginModal(); setMobileOpen(false); }}
                      className="w-full rounded-lg bg-emerald py-2 text-center text-sm font-semibold text-void"
                    >
                      Sign In with Gmail
                    </button>
                  )}
                </li>
              </ul>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      {/* Mobile bottom navigation */}
      <nav
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border-soft bg-void/90 backdrop-blur-xl md:hidden"
        style={{ paddingBottom: "env(safe-area-inset-bottom, 0px)" }}
      >
        <ul className="flex items-center justify-around px-2 py-1.5">
          {NAV_LINKS.map((link) => {
            const isActive =
              link.end
                ? location.pathname === link.to
                : location.pathname.startsWith(link.to);
            return (
              <li key={link.to}>
                <NavLink
                  to={link.to}
                  end={link.end}
                  className="flex flex-col items-center gap-0.5 rounded-lg px-3 py-1.5 transition-colors"
                >
                  {(() => { const Icon = link.icon; return (
                    <Icon
                      size={20}
                      className={cn(
                        "transition-colors",
                        isActive ? "text-emerald" : "text-ink-tertiary",
                      )}
                    />
                  ); })()}
                  <span
                    className={cn(
                      "text-[10px] font-medium",
                      isActive ? "text-emerald" : "text-ink-tertiary",
                    )}
                  >
                    {link.label}
                  </span>
                  {isActive && (
                    <motion.div
                      layoutId="bottom-nav-dot"
                      className="absolute -top-px h-0.5 w-6 rounded-full bg-emerald"
                      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                    />
                  )}
                </NavLink>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
