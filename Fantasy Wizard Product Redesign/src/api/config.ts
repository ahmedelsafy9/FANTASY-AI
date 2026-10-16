const DEFAULT_PROD_API_URL = "https://fantasy-ai.fly.dev"
const DEFAULT_DEV_API_URL = "http://localhost:8000"

export function resolveApiUrl(): string {
  const custom = import.meta.env.VITE_API_URL?.trim()
  if (custom) return custom.replace(/\/+$/, "")
  return import.meta.env.PROD ? DEFAULT_PROD_API_URL : DEFAULT_DEV_API_URL
}

export const API_BASE_URL = resolveApiUrl()

/** Explicit mock mode. Never used as a silent fallback after an API failure. */
export function isMockMode(): boolean {
  return import.meta.env.VITE_USE_MOCK === "true"
}
