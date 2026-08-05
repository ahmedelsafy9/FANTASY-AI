/**
 * Auth-related type definitions for Gmail-only authentication.
 *
 * Users can ONLY authenticate via the real Google OAuth 2.0 flow.
 * Google verifies identity; we additionally enforce that the verified
 * email belongs to the @gmail.com domain.
 */

/** A successfully authenticated Gmail user profile. */
export interface GmailUser {
  /** Display name from the Google account. */
  name: string;
  /** Verified email — always ends with @gmail.com. */
  email: string;
  /** Google profile picture URL. */
  picture: string;
  /** ISO timestamp of when the user signed in. */
  loginTime: string;
}

/** Shape of the auth context exposed to consumers. */
export interface AuthContextType {
  /** The currently authenticated user, or `null` if signed out. */
  user: GmailUser | null;
  /** Convenience boolean — `true` when `user` is not `null`. */
  isAuthenticated: boolean;
  /** Sign out and clear the session. */
  logout: () => void;
  /** Open the sign-in modal. */
  openLoginModal: () => void;
  /** Close the sign-in modal. */
  closeLoginModal: () => void;
  /** Whether the login modal is currently visible. */
  isLoginModalOpen: boolean;
}

/**
 * The credential response object returned by the Google Identity
 * Services `google.accounts.id.initialize` callback.
 */
export interface GoogleCredentialResponse {
  credential: string;
  select_by?: string;
}

/** Decoded payload from a Google ID token JWT. */
export interface GoogleJwtPayload {
  sub: string;
  name?: string;
  email?: string;
  email_verified?: boolean;
  picture?: string;
  iss?: string;
  aud?: string;
  exp?: number;
  iat?: number;
}
