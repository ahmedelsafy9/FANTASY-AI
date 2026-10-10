import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  Users,
  LayoutDashboard,
  Shirt,
  Crown,
  Trophy,
  Menu,
  X,
  LogOut,
  UserCheck,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { path: "/", label: "Overview", icon: LayoutDashboard },
  { path: "/squad", label: "My Team", icon: Shirt },
  { path: "/players", label: "Player Analytics", icon: Users },
  { path: "/match-predictions", label: "Match Predictions", icon: Trophy },
  { path: "/captain", label: "Captain", icon: Crown },
];

export function Navigation() {
  const location = useLocation();
  const { user, isAuthenticated, logout, openLoginModal } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 w-full border-b border-[#E8E3ED] bg-white shadow-soft">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Logo */}
        <Link
          to="/"
          className="flex items-center gap-2.5 transition-transform hover:scale-105 active:scale-95"
        >
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#452477] text-white shadow-sm border border-[#7041C5]">
            <Sparkles size={18} className="fill-[#B9DDF5] text-[#B9DDF5]" />
          </div>
          <span className="font-display text-xl font-black tracking-tight text-[#19171D]">
            FANTASY<span className="text-[#7041C5] font-black">.AI</span>
          </span>
        </Link>

        {/* Desktop Nav Links */}
        <nav className="hidden items-center gap-1.5 md:flex">
          {NAV_ITEMS.map((item) => {
            const isActive = location.pathname === item.path;
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "relative flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-xs font-black transition-all duration-150",
                  isActive
                    ? "bg-[#EEE7FA] text-[#452477] border border-[#D8C7F4] shadow-xs"
                    : "text-[#6F6A76] hover:text-[#19171D] hover:bg-[#F8F7FA]",
                )}
              >
                <Icon size={14} className={isActive ? "text-[#7041C5]" : "text-[#938E9B]"} />
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* User Auth Section */}
        <div className="hidden items-center gap-3 md:flex">
          {isAuthenticated && user ? (
            <div className="flex items-center gap-2.5 rounded-full border border-[#E8E3ED] bg-[#F8F7FA] p-1 pr-3.5 shadow-sm">
              <img
                src={user.picture}
                alt={user.name}
                className="h-7 w-7 rounded-full border-2 border-[#7041C5]"
              />
              <span className="text-xs font-black text-[#19171D] max-w-[120px] truncate">
                {user.name}
              </span>
              <button
                onClick={logout}
                title="Sign Out"
                className="ml-1 rounded-full p-1 text-[#6F6A76] hover:bg-red-50 hover:text-[#DC2626] transition-colors cursor-pointer"
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
          className="flex h-10 w-10 items-center justify-center rounded-xl border border-[#E8E3ED] bg-[#F8F7FA] text-[#19171D] md:hidden shadow-sm hover:bg-[#EEE7FA] cursor-pointer"
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
            className="border-b border-[#E8E3ED] bg-white px-4 py-4 md:hidden shadow-card-hover"
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
                        ? "bg-[#EEE7FA] text-[#452477] border border-[#D8C7F4]"
                        : "text-[#6F6A76] hover:bg-[#F8F7FA] hover:text-[#19171D]",
                    )}
                  >
                    <Icon size={16} className={isActive ? "text-[#7041C5]" : "text-[#938E9B]"} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>

            <div className="mt-4 pt-4 border-t border-[#E8E3ED]">
              {isAuthenticated && user ? (
                <div className="flex items-center justify-between rounded-xl bg-[#F8F7FA] p-2.5 border border-[#E8E3ED]">
                  <div className="flex items-center gap-2.5">
                    <img
                      src={user.picture}
                      alt={user.name}
                      className="h-8 w-8 rounded-full border-2 border-[#7041C5]"
                    />
                    <div className="flex flex-col">
                      <span className="text-xs font-black text-[#19171D]">{user.name}</span>
                      <span className="text-[10px] font-bold text-[#6F6A76]">{user.email}</span>
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
