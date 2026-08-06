import axios from "axios";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_URL,
  timeout: 15000,
});

/** True when running against the real backend rather than mock data. */
export const API_BASE_URL = API_URL;
