/**
 * Differential prediction types mirroring the backend schema
 * (src/api/schemas.py).
 */

export interface DifferentialPlayer {
  element?: number | null;
  name: string;
  team: string;
  position?: string | null;
  price?: number | null;
  value?: number | null;
  ownership_pct?: number | null;
  ownership_percentile?: number | null;
  predicted_expected_points?: number | null;
  p_6_plus?: number | null;
  p_8_plus?: number | null;
  p_10_plus?: number | null;
  p_12_plus?: number | null;
  differential_score: number;
  differential_category: "Elite Differential" | "Value Differential" | "Emerging Differential" | "Standard Differential" | string;
  predicted_gameweek?: number | null;
  photo_url?: string | null;
}

export interface DifferentialListResponse {
  count: number;
  season?: string | null;
  latest_completed_gameweek?: number | null;
  predicted_gameweek?: number | null;
  generated_at?: string | null;
  predictions: DifferentialPlayer[];
}
