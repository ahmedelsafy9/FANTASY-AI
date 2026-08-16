import axios from "axios";

const DEFAULT_PROD_API_URL = "https://fantasy-ai.fly.dev";
const DEFAULT_DEV_API_URL = "http://localhost:8000";

/**
 * Resolves the backend API base URL:
 * - Uses `VITE_API_URL` if explicitly provided (e.g. from Vercel env or local .env).
 * - Falls back to production backend `https://fantasy-ai.fly.dev` in production builds (`import.meta.env.PROD`).
 * - Falls back to `http://localhost:8000` during local development.
 */
const resolveApiUrl = (): string => {
  const customUrl = import.meta.env.VITE_API_URL?.trim();
  if (customUrl) {
    return customUrl.replace(/\/+$/, "");
  }
  return import.meta.env.PROD ? DEFAULT_PROD_API_URL : DEFAULT_DEV_API_URL;
};

const API_URL = resolveApiUrl();

export const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 15000,
});

/** True when running against the real backend rather than mock data. */
export const API_BASE_URL = API_URL;
