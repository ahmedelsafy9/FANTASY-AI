import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { CheckCircle, AlertTriangle, X } from "lucide-react";
import { AUTH_EVENT, AUTH_ERROR_EVENT } from "@/context/AuthContext";
import { cn } from "@/lib/utils";

/* -------------------------------------------------------------------------- */
/* Toast types                                                                 */
/* -------------------------------------------------------------------------- */

interface ToastItem {
  id: number;
  message: string;
  variant: "success" | "error";
}

let nextId = 0;

/* -------------------------------------------------------------------------- */
/* Toast container — listens for auth events automatically                    */
/* -------------------------------------------------------------------------- */

export function AuthToast() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const timers = useRef<Map<number, ReturnType<typeof setTimeout>>>(new Map());

  const push = (message: string, variant: ToastItem["variant"]) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, message, variant }]);
    const timer = setTimeout(() => dismiss(id), 5000);
    timers.current.set(id, timer);
  };

  const dismiss = (id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
    const timer = timers.current.get(id);
    if (timer) {
      clearTimeout(timer);
      timers.current.delete(id);
    }
  };

  useEffect(() => {
    function onAuthChange(e: Event) {
      const user = (e as CustomEvent).detail;
      if (user) {
        push(`Welcome, ${user.name}! Signed in with ${user.email}`, "success");
      } else {
        push("Signed out successfully.", "success");
      }
    }

    function onAuthError(e: Event) {
      const message = (e as CustomEvent).detail as string;
      push(message, "error");
    }

    window.addEventListener(AUTH_EVENT, onAuthChange);
    window.addEventListener(AUTH_ERROR_EVENT, onAuthError);
    return () => {
      window.removeEventListener(AUTH_EVENT, onAuthChange);
      window.removeEventListener(AUTH_ERROR_EVENT, onAuthError);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-6 right-6 z-[60] flex flex-col items-end gap-3"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            layout
            initial={{ opacity: 0, y: 16, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -8, scale: 0.95 }}
            transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              "pointer-events-auto flex max-w-sm items-start gap-3 rounded-xl border px-4 py-3 shadow-card",
              toast.variant === "success"
                ? "border-teal/25 bg-teal/10 text-teal"
                : "border-coral/25 bg-coral/10 text-coral",
            )}
          >
            {toast.variant === "success" ? (
              <CheckCircle size={18} className="mt-0.5 shrink-0" />
            ) : (
              <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            )}
            <p className="text-sm font-medium leading-snug text-ink">
              {toast.message}
            </p>
            <button
              onClick={() => dismiss(toast.id)}
              className="ml-auto shrink-0 rounded-md p-1 text-ink-tertiary transition-colors hover:text-ink"
              aria-label="Dismiss"
            >
              <X size={14} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
