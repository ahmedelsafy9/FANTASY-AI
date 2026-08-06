import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X, ShieldAlert, Mail, Info, CheckCircle } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { AUTH_ERROR_EVENT } from "@/context/AuthContext";

/* -------------------------------------------------------------------------- */
/* Google Icon (inline SVG)                                                   */
/* -------------------------------------------------------------------------- */

function GoogleIcon({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
        fill="#4285F4"
      />
      <path
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
        fill="#34A853"
      />
      <path
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
        fill="#FBBC05"
      />
      <path
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
        fill="#EA4335"
      />
    </svg>
  );
}

/* -------------------------------------------------------------------------- */
/* LoginModal                                                                  */
/* -------------------------------------------------------------------------- */

export function LoginModal() {
  const { isLoginModalOpen, closeLoginModal } = useAuth();
  const googleBtnRef = useRef<HTMLDivElement>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [testEmail, setTestEmail] = useState("");
  const [testName, setTestName] = useState("");
  const [showGuide, setShowGuide] = useState(false);

  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const hasClientId = !!clientId && !clientId.includes("your-client-id");

  /* ---- Render official Google button when modal opens -------------------- */

  useEffect(() => {
    if (!isLoginModalOpen || !hasClientId || !googleBtnRef.current) return;

    function tryRender() {
      if (!window.google?.accounts?.id || !googleBtnRef.current) return false;
      googleBtnRef.current.innerHTML = "";
      window.google.accounts.id.renderButton(googleBtnRef.current, {
        theme: "filled_black",
        size: "large",
        type: "standard",
        shape: "pill",
        text: "signin_with",
        logo_alignment: "left",
        width: 320,
      });
      return true;
    }

    if (tryRender()) return;

    const interval = setInterval(() => {
      if (tryRender()) clearInterval(interval);
    }, 200);
    const timeout = setTimeout(() => clearInterval(interval), 8000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [isLoginModalOpen, hasClientId]);

  /* ---- Listen for auth errors from context ------------------------------ */

  useEffect(() => {
    function onError(e: Event) {
      setAuthError((e as CustomEvent).detail as string);
    }
    window.addEventListener(AUTH_ERROR_EVENT, onError);
    return () => window.removeEventListener(AUTH_ERROR_EVENT, onError);
  }, []);

  useEffect(() => {
    setAuthError(null);
  }, [isLoginModalOpen]);

  /* ---- Demo Email Validation (Strict Gmail Only) ------------------------- */

  const handleTestSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    const email = testEmail.trim().toLowerCase();

    if (!email) {
      setAuthError("Please enter your Gmail address.");
      return;
    }

    if (!email.endsWith("@gmail.com") || !/^[a-z0-9._%+-]+@gmail\.com$/i.test(email)) {
      setAuthError(`Access Denied: "${email}" is not a valid @gmail.com address. Only Gmail accounts are permitted.`);
      return;
    }

    // Dispatch simulated verified Gmail user
    const name = testName.trim() || email.split("@")[0];
    const userProfile = {
      name: name.charAt(0).toUpperCase() + name.slice(1),
      email: email,
      picture: `https://api.dicebear.com/9.x/initials/svg?seed=${encodeURIComponent(name)}`,
      loginTime: new Date().toISOString(),
    };

    localStorage.setItem("fantasy_ai_gmail_user", JSON.stringify(userProfile));
    window.dispatchEvent(new CustomEvent("fantasy-ai:auth-change", { detail: userProfile }));
    closeLoginModal();
  };

  if (!isLoginModalOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="absolute inset-0 bg-void/80 backdrop-blur-sm"
          onClick={closeLoginModal}
          aria-hidden="true"
        />

        {/* Dialog */}
        <motion.div
          role="dialog"
          aria-modal="true"
          aria-label="Sign in to Fantasy-AI"
          initial={{ opacity: 0, scale: 0.96, y: 8 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.96, y: 8 }}
          transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="glass relative z-10 w-full max-w-md overflow-hidden rounded-2xl border border-border-medium shadow-card"
        >
          {/* Close button */}
          <button
            onClick={closeLoginModal}
            aria-label="Close"
            className="absolute right-4 top-4 z-10 rounded-lg p-1.5 text-ink-secondary transition-colors hover:bg-white/5 hover:text-ink"
          >
            <X size={18} />
          </button>

          {/* Header */}
          <div className="px-8 pb-2 pt-8 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gold/10 shadow-glow">
              <Mail size={24} className="text-gold" />
            </div>
            <h2 className="font-display text-xl font-semibold tracking-tight text-ink">
              Sign in to Fantasy<span className="text-gold">-AI</span>
            </h2>
            <p className="mt-1.5 text-sm text-ink-secondary">
              Strict Gmail-Only Account Verification
            </p>
          </div>

          {/* Gmail restriction notice */}
          <div className="mx-8 mt-4 flex items-start gap-3 rounded-xl border border-coral/25 bg-coral/10 px-4 py-3">
            <ShieldAlert size={18} className="mt-0.5 shrink-0 text-coral" />
            <p className="text-xs leading-relaxed text-ink-secondary">
              <span className="font-semibold text-ink">Strict Gmail Policy:</span> Only accounts ending with <strong className="text-coral font-mono">@gmail.com</strong> are allowed to sign in.
            </p>
          </div>

          <div className="px-8 pb-8 pt-5">
            {hasClientId ? (
              /* Configured OAuth mode */
              <div className="flex flex-col items-center gap-4">
                <div ref={googleBtnRef} id="google-signin-button" />
                <button
                  type="button"
                  onClick={() => window.google?.accounts?.id?.prompt()}
                  className="flex w-full items-center justify-center gap-3 rounded-xl border border-border-medium bg-surface-elevated px-5 py-3 text-sm font-medium text-ink transition-all duration-200 hover:bg-surface-hover active:scale-[0.98]"
                >
                  <GoogleIcon className="h-5 w-5" />
                  Sign in with Google
                </button>
              </div>
            ) : (
              /* Client ID setup guide + Direct Gmail validator form */
              <div className="flex flex-col gap-4">
                <form onSubmit={handleTestSubmit} className="flex flex-col gap-3">
                  <div>
                    <label className="mb-1 block text-xs font-medium text-ink-secondary">
                      Enter your Gmail address (@gmail.com required)
                    </label>
                    <input
                      type="email"
                      value={testEmail}
                      onChange={(e) => setTestEmail(e.target.value)}
                      placeholder="yourname@gmail.com"
                      required
                      className="w-full rounded-xl border border-border-medium bg-surface px-4 py-2.5 text-sm text-ink outline-none transition-colors focus:border-gold"
                    />
                  </div>

                  <div>
                    <label className="mb-1 block text-xs font-medium text-ink-secondary">
                      Display Name (Optional)
                    </label>
                    <input
                      type="text"
                      value={testName}
                      onChange={(e) => setTestName(e.target.value)}
                      placeholder="e.g. Alex Smith"
                      className="w-full rounded-xl border border-border-medium bg-surface px-4 py-2.5 text-sm text-ink outline-none transition-colors focus:border-gold"
                    />
                  </div>

                  <button
                    type="submit"
                    className="mt-1 flex w-full items-center justify-center gap-2 rounded-xl bg-gold py-2.5 text-sm font-semibold text-void shadow-glow transition-all hover:bg-gold-bright active:scale-[0.98]"
                  >
                    <GoogleIcon className="h-4 w-4" />
                    Sign In with Gmail
                  </button>
                </form>

                {/* Free Setup Info Toggle */}
                <div className="border-t border-border-soft pt-3 text-center">
                  <button
                    type="button"
                    onClick={() => setShowGuide(!showGuide)}
                    className="inline-flex items-center gap-1.5 text-xs text-ink-tertiary hover:text-gold transition-colors"
                  >
                    <Info size={14} />
                    {showGuide ? "Hide Google Cloud Setup Guide" : "Want real Google popup? Setup is 100% Free"}
                  </button>

                  {showGuide && (
                    <div className="mt-3 rounded-xl border border-border-soft bg-surface p-4 text-left text-xs leading-relaxed text-ink-secondary">
                      <p className="font-semibold text-teal flex items-center gap-1 mb-1">
                        <CheckCircle size={14} /> Google Cloud OAuth is 100% Free!
                      </p>
                      <p className="mb-2">No credit card or payment is required. Follow these steps:</p>
                      <ol className="list-decimal list-inside space-y-1 text-ink-tertiary">
                        <li>Go to <a href="https://console.cloud.google.com/" target="_blank" rel="noreferrer" className="text-gold underline">console.cloud.google.com</a></li>
                        <li>Create a project (e.g. "Fantasy AI")</li>
                        <li>Go to <strong>APIs & Services &gt; OAuth consent screen</strong> (choose External)</li>
                        <li>Go to <strong>Credentials &gt; Create Credentials &gt; OAuth client ID</strong></li>
                        <li>Choose <strong>Web application</strong> &amp; add origin <code className="text-gold">http://localhost:5173</code></li>
                        <li>Copy the Client ID into <code className="text-gold">.env</code> as <code className="text-gold">VITE_GOOGLE_CLIENT_ID</code></li>
                      </ol>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Error banner */}
            <AnimatePresence>
              {authError && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: "auto" }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-4 overflow-hidden rounded-xl border border-coral/25 bg-coral/10 px-4 py-3"
                >
                  <p className="text-xs font-medium text-coral">{authError}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
