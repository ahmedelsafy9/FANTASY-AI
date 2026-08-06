import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type {
  AuthContextType,
  GmailUser,
  GoogleCredentialResponse,
  GoogleJwtPayload,
} from "@/types/auth";

/* -------------------------------------------------------------------------- */
/* Constants                                                                   */
/* -------------------------------------------------------------------------- */

const STORAGE_KEY = "fantasy_ai_gmail_user";
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as
  | string
  | undefined;

/* -------------------------------------------------------------------------- */
/* Helpers                                                                     */
/* -------------------------------------------------------------------------- */

/** Returns `true` only for addresses with the exact domain `gmail.com`. */
function isGmailAddress(email: string): boolean {
  return /^[a-z0-9._%+-]+@gmail\.com$/i.test(email.trim());
}

/**
 * Decode the Base64-URL–encoded payload of a JWT **without** verifying
 * the signature. Signature verification is not needed client-side because
 * the token comes directly from Google over HTTPS — the authenticity is
 * guaranteed by the transport, not by the client re-checking the RSA sig.
 */
function decodeJwtPayload(token: string): GoogleJwtPayload | null {
  try {
    const base64Url = token.split(".")[1];
    const base64 = base64Url.replace(/-/g, "+").replace(/_/g, "/");
    const json = decodeURIComponent(
      atob(base64)
        .split("")
        .map((c) => "%" + ("00" + c.charCodeAt(0).toString(16)).slice(-2))
        .join(""),
    );
    return JSON.parse(json) as GoogleJwtPayload;
  } catch {
    return null;
  }
}

/* -------------------------------------------------------------------------- */
/* Context                                                                     */
/* -------------------------------------------------------------------------- */

const AuthContext = createContext<AuthContextType | null>(null);

/**
 * Consume the auth context. Must be called inside `<AuthProvider>`.
 */
export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider.");
  return ctx;
}

/* -------------------------------------------------------------------------- */
/* Provider                                                                    */
/* -------------------------------------------------------------------------- */

interface AuthProviderProps {
  children: ReactNode;
}

/** Toast-style callback the provider exposes so the LoginModal can show errors. */
export type AuthErrorCallback = (message: string) => void;

/**
 * Global event name fired when auth state changes. The LoginModal and
 * Toast components listen for this to react accordingly.
 */
export const AUTH_EVENT = "fantasy-ai:auth-change" as const;
export const AUTH_ERROR_EVENT = "fantasy-ai:auth-error" as const;

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<GmailUser | null>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (!stored) return null;
      const parsed = JSON.parse(stored) as GmailUser;
      // Re-validate on hydration — if the stored email is somehow not
      // gmail.com any more, treat as logged-out.
      if (!parsed.email || !isGmailAddress(parsed.email)) return null;
      return parsed;
    } catch {
      return null;
    }
  });

  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);

  /* ---- session helpers --------------------------------------------------- */

  const persistUser = useCallback((u: GmailUser | null) => {
    setUser(u);
    if (u) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(u));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    window.dispatchEvent(new CustomEvent(AUTH_EVENT, { detail: u }));
  }, []);

  const logout = useCallback(() => {
    persistUser(null);
    setIsLoginModalOpen(false);
  }, [persistUser]);

  const openLoginModal = useCallback(() => setIsLoginModalOpen(true), []);
  const closeLoginModal = useCallback(() => setIsLoginModalOpen(false), []);

  /* ---- Google Identity Services callback -------------------------------- */

  const handleGoogleCredential = useCallback(
    (response: GoogleCredentialResponse) => {
      if (!response.credential) {
        window.dispatchEvent(
          new CustomEvent(AUTH_ERROR_EVENT, {
            detail: "Google authentication failed. No credential received.",
          }),
        );
        return;
      }

      const payload = decodeJwtPayload(response.credential);
      if (!payload || !payload.email) {
        window.dispatchEvent(
          new CustomEvent(AUTH_ERROR_EVENT, {
            detail: "Could not read your Google profile. Please try again.",
          }),
        );
        return;
      }

      // Google has verified this user owns this email. Now enforce Gmail-only.
      if (!isGmailAddress(payload.email)) {
        window.dispatchEvent(
          new CustomEvent(AUTH_ERROR_EVENT, {
            detail: `Access denied — "${payload.email}" is not a @gmail.com account. Only Gmail users can sign in.`,
          }),
        );
        return;
      }

      const gmailUser: GmailUser = {
        name: payload.name ?? payload.email.split("@")[0],
        email: payload.email.toLowerCase(),
        picture:
          payload.picture ??
          `https://api.dicebear.com/9.x/initials/svg?seed=${encodeURIComponent(payload.name ?? payload.email)}`,
        loginTime: new Date().toISOString(),
      };

      persistUser(gmailUser);
      setIsLoginModalOpen(false);
    },
    [persistUser],
  );

  /* ---- Initialize Google SDK once --------------------------------------- */

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;

    // The GSI library loads async; wait for it.
    function tryInit() {
      if (!window.google?.accounts?.id) return false;
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID!,
        callback: handleGoogleCredential as (
          resp: GoogleCredentialResponse,
        ) => void,
        auto_select: false,
        cancel_on_tap_outside: true,
      });
      return true;
    }

    if (tryInit()) return;

    // If the script hasn't loaded yet, poll briefly.
    const interval = setInterval(() => {
      if (tryInit()) clearInterval(interval);
    }, 200);
    const timeout = setTimeout(() => clearInterval(interval), 10_000);

    return () => {
      clearInterval(interval);
      clearTimeout(timeout);
    };
  }, [handleGoogleCredential]);

  /* ---- Context value ---------------------------------------------------- */

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      isAuthenticated: user !== null,
      logout,
      openLoginModal,
      closeLoginModal,
      isLoginModalOpen,
    }),
    [user, logout, openLoginModal, closeLoginModal, isLoginModalOpen],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/* -------------------------------------------------------------------------- */
/* Global type augmentation for google.accounts                               */
/* -------------------------------------------------------------------------- */

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string;
            callback: (response: GoogleCredentialResponse) => void;
            auto_select?: boolean;
            cancel_on_tap_outside?: boolean;
          }) => void;
          renderButton: (
            parent: HTMLElement,
            options: {
              theme?: string;
              size?: string;
              type?: string;
              shape?: string;
              text?: string;
              logo_alignment?: string;
              width?: number;
            },
          ) => void;
          prompt: () => void;
          disableAutoSelect: () => void;
        };
      };
    };
  }
}
