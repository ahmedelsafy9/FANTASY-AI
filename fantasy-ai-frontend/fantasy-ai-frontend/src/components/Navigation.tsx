import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Users,
  LayoutDashboard,
  Shirt,
  Crown,
  Trophy,
  Menu,
  X,
  LogOut,
  UserCheck,
  Sparkles,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/primitives";
import { WizardBrandMark } from "@/components/brand/WizardBrandMark";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { path: "/", label: "Overview", icon: LayoutDashboard },
  { path: "/players", label: "Player Analytics", icon: Users },
  { path: "/match-predictions", label: "Match Predictions", icon: Trophy },
  { path: "/squad", label: "Squad Builder", icon: Shirt },
  { path: "/captain", label: "Captain", icon: Crown },
  { path: "/assistant", label: "AI Assistant", icon: Sparkles, highlight: true },
];

export function Navigation() {
  const location = useLocation();
  const { user, isAuthenticated, logout, openLoginModal } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-border bg-ivory-surface shadow-card backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand Logo & Wordmark */}
        <Link
          to="/"
          className="transition-transform hover:scale-102 active:scale-98 focus:outline-none focus-visible:ring-2 focus-visible:ring-gold-metallic rounded-xl"
        >
          <WizardBrandMark size="md" />
        </Link>

        {/* Desktop Navigation Links */}
        <nav className="hidden items-center gap-1 lg:gap-1.5 md:flex">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "relative flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-black transition-all duration-150 select-none",
                  isActive
                    ? "bg-stadium-deep text-ivory-surface shadow-xs border border-stadium-surface"
                    : item.highlight
                    ? "text-gold-dark bg-gold-light/60 border border-gold-border/60 hover:bg-gold-light hover:border-gold-metallic"
                    : "text-ink-secondary hover:text-ink-primary hover:bg-ivory-subtle",
                )}
              >
                <Icon
                  size={14}
                  className={cn(
                    isActive
                      ? "text-gold-bright"
                      : item.highlight
                      ? "text-gold-metallic"
                      : "text-ink-secondary",
                  )}
                />
                <span>{item.label}</span>
                {item.highlight && !isActive && (
                  <span className="flex h-1.5 w-1.5 rounded-full bg-gold-metallic" />
                )}
              </Link>
            );
          })}
        </nav>

        {/* User Auth Section */}
        <div className="hidden items-center gap-3 md:flex">
          {isAuthenticated && user ? (
            <div className="flex items-center gap-2.5 rounded-full border border-border bg-ivory-subtle p-1 pr-3.5 shadow-xs">
              <img
                src={user.picture}
                alt={user.name}
                className="h-7 w-7 rounded-full border-2 border-gold-metallic object-cover"
              />
              <span className="text-xs font-black text-ink-primary max-w-[120px] truncate">
                {user.name}
              </span>
              <button
                onClick={logout}
                title="Sign Out"
                className="ml-1 rounded-full p-1 text-ink-secondary hover:bg-red-50 hover:text-rose-700 transition-colors cursor-pointer"
              >
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <Button
              variant="primary"
              size="sm"
              onClick={openLoginModal}
              className="gap-1.5"
            >
              <UserCheck size={14} />
              <span>Sign In</span>
            </Button>
          )}
        </div>

        {/* Mobile Menu Button */}
        <button
          onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-border bg-ivory-subtle text-ink-primary md:hidden shadow-xs hover:bg-ivory-surface cursor-pointer"
          aria-label="Toggle Menu"
        >
          {mobileMenuOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="border-b border-border bg-ivory-surface px-4 py-4 md:hidden shadow-card-hover"
          >
            <nav className="flex flex-col gap-1.5">
              {NAV_ITEMS.map((item) => {
                const isActive = location.pathname === item.path;
                const Icon = item.icon;
                return (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setMobileMenuOpen(false)}
                    className={cn(
                      "flex items-center gap-3 rounded-xl px-3.5 py-2.5 text-sm font-black transition-all",
                      isActive
                        ? "bg-stadium-deep text-ivory-surface border border-stadium-surface"
                        : item.highlight
                        ? "bg-gold-light text-gold-dark border border-gold-border"
                        : "text-ink-secondary hover:bg-ivory-subtle hover:text-ink-primary",
                    )}
                  >
                    <Icon
                      size={16}
                      className={isActive ? "text-gold-bright" : item.highlight ? "text-gold-metallic" : "text-ink-secondary"}
                    />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="mt-4 pt-4 border-t border-border">
              {isAuthenticated && user ? (
                <div className="flex items-center justify-between rounded-xl bg-ivory-subtle p-2.5 border border-border">
                  <div className="flex items-center gap-2.5">
                    <img
                      src={user.picture}
                      alt={user.name}
                      className="h-8 w-8 rounded-full border-2 border-gold-metallic object-cover"
                    />
                    <div className="flex flex-col">
                      <span className="text-xs font-black text-ink-primary">{user.name}</span>
                      <span className="text-[10px] font-bold text-ink-secondary">{user.email}</span>
                    </div>
                  </div>
                  <Button variant="ghost" size="sm" onClick={logout}>
                    <LogOut size={14} />
                  </Button>
                </div>
              ) : (
                <Button
                  variant="primary"
                  className="w-full justify-center"
                  onClick={() => {
                    setMobileMenuOpen(false);
                    openLoginModal();
                  }}
                >
                  <UserCheck size={16} />
                  <span>Sign In with Google</span>
                </Button>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
