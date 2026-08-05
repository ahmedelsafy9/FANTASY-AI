import { useState } from "react";
import { NavLink } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Zap, LogOut, CheckCircle2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/primitives";

const LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/predictions", label: "Predictions" },
  { to: "/players", label: "Players" },
  { to: "/fixtures", label: "Fixtures" },
  { to: "/about", label: "About" },
];

export function Navigation() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const { user, logout, openLoginModal } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-border-soft bg-void/80 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
        <NavLink to="/" className="flex items-center gap-2" aria-label="Fantasy-AI home">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gold/10 text-gold">
            <Zap size={17} strokeWidth={2.5} />
          </div>
          <span className="font-display text-lg font-semibold tracking-tight text-ink">
            Fantasy<span className="text-gold">-AI</span>
          </span>
        </NavLink>

        <ul className="hidden items-center gap-1 md:flex">
          {LINKS.map((link) => (
            <li key={link.to}>
              <NavLink
                to={link.to}
                end={link.end}
                className={({ isActive }) =>
                  cn(
                    "relative rounded-lg px-3.5 py-2 text-sm font-medium transition-colors",
                    isActive ? "text-ink" : "text-ink-secondary hover:text-ink",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    {link.label}
                    {isActive && (
                      <motion.span
                        layoutId="nav-active"
                        className="absolute inset-x-3 -bottom-[1px] h-[2px] rounded-full bg-gold"
                        transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
                      />
                    )}
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>

        {/* Right Side Auth Widget */}
        <div className="hidden items-center gap-3 md:flex">
          {user ? (
            <div className="flex items-center gap-3 rounded-full border border-border-medium bg-surface px-3 py-1.5 shadow-sm">
              <img
                src={user.picture}
                alt={user.name}
                className="h-7 w-7 rounded-full object-cover ring-2 ring-gold/40"
              />
              <div className="flex flex-col text-left">
                <span className="text-xs font-semibold leading-tight text-ink">
                  {user.name}
                </span>
                <span className="flex items-center gap-1 text-[10px] font-medium text-teal">
                  <CheckCircle2 size={10} /> Gmail Verified
                </span>
              </div>
              <button
                onClick={logout}
                title="Sign out"
                aria-label="Sign out"
                className="ml-1 rounded-full p-1 text-ink-tertiary transition-colors hover:bg-coral/10 hover:text-coral"
              >
                <LogOut size={15} />
              </button>
            </div>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={openLoginModal}
              className="rounded-full shadow-glow"
            >
              Sign In with Gmail
            </Button>
          )}
        </div>

        <button
          className="rounded-lg p-2 text-ink md:hidden"
          onClick={() => setMobileOpen((o) => !o)}
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
          aria-expanded={mobileOpen}
        >
          {mobileOpen ? <X size={22} /> : <Menu size={22} />}
        </button>
      </nav>

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
              {LINKS.map((link) => (
                <li key={link.to}>
                  <NavLink
                    to={link.to}
                    end={link.end}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        "block rounded-lg px-3 py-2.5 text-base font-medium transition-colors",
                        isActive ? "bg-gold/10 text-gold" : "text-ink-secondary hover:bg-surface hover:text-ink",
                      )
                    }
                  >
                    {link.label}
                  </NavLink>
                </li>
              ))}
              <li className="pt-2 border-t border-border-soft">
                {user ? (
                  <div className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2">
                      <img src={user.picture} alt={user.name} className="h-8 w-8 rounded-full object-cover" />
                      <div className="flex flex-col">
                        <span className="text-sm font-semibold text-ink">{user.name}</span>
                        <span className="text-xs text-teal">{user.email}</span>
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
                  <Button
                    variant="primary"
                    size="md"
                    onClick={() => { openLoginModal(); setMobileOpen(false); }}
                    className="w-full justify-center"
                  >
                    Sign In with Gmail
                  </Button>
                )}
              </li>
            </ul>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
